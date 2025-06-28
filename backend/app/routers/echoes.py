"""
Enhanced Echoes API endpoints with improved service layer integration
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime

from app.models.echo import (
    Echo,
    EchoCreate,
    EchoResponse,
    EchoListResponse,
    PresignedUrlRequest,
    PresignedUrlResponse,
    EmotionType
)
from app.models.user import UserContext, ErrorResponse
from app.services.echo_service import (
    echo_service,
    EchoServiceError,
    EchoNotFoundError,
    EchoValidationError
)
from app.services.cognito_service import cognito_service
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()
security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserContext:
    """
    Dependency to get current authenticated user
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        UserContext for the authenticated user
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        token = credentials.credentials
        token_data = cognito_service.verify_token(token)
        user_context = cognito_service.get_user_context(token_data)
        
        logger.debug(f"Authenticated user: {user_context.user_id}")
        return user_context
        
    except ValueError as e:
        logger.warning(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Unexpected authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )


@router.post(
    "/echoes/init-upload",
    response_model=PresignedUrlResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initialize audio upload",
    description="Generate a presigned URL for uploading audio files to S3",
    responses={
        201: {"description": "Presigned URL generated successfully"},
        400: {"description": "Invalid file format or request data"},
        401: {"description": "Authentication required"},
        500: {"description": "Internal server error"}
    }
)
async def init_upload(
    request: PresignedUrlRequest,
    current_user: UserContext = Depends(get_current_user)
) -> PresignedUrlResponse:
    """
    Generate presigned URL for audio file upload
    
    This endpoint generates a presigned S3 URL that allows the client to upload
    audio files directly to S3. The URL expires after a configurable time period.
    
    Args:
        request: Upload request with file details
        current_user: Authenticated user context
        
    Returns:
        Presigned URL response with upload details
        
    Raises:
        HTTPException: If S3 operation fails
    """
    try:
        presigned_response = await echo_service.init_upload(
            user_id=current_user.user_id,
            request=request
        )
        
        logger.info(f"Generated presigned URL for echo {presigned_response.echo_id}")
        return presigned_response
        
    except EchoValidationError as e:
        logger.warning(f"Validation error in init_upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except EchoServiceError as e:
        logger.error(f"Service error in init_upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in init_upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate upload URL"
        )


@router.post(
    "/echoes",
    response_model=EchoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new echo",
    description="Save echo metadata after successful audio upload",
    responses={
        201: {"description": "Echo created successfully"},
        400: {"description": "Invalid echo data or echo ID"},
        401: {"description": "Authentication required"},
        500: {"description": "Internal server error"}
    }
)
async def create_echo(
    echo_data: EchoCreate,
    echo_id: str = Query(..., description="Echo ID from init-upload response"),
    current_user: UserContext = Depends(get_current_user)
) -> EchoResponse:
    """
    Create a new echo with metadata
    
    This endpoint saves echo metadata to DynamoDB after the audio file has been
    successfully uploaded to S3 using the presigned URL.
    
    Args:
        echo_data: Echo creation data
        echo_id: Echo ID from the init-upload response
        current_user: Authenticated user context
        
    Returns:
        Created echo response
        
    Raises:
        HTTPException: If creation fails or echo_id is invalid
    """
    try:
        echo_response = await echo_service.create_echo(
            user_id=current_user.user_id,
            echo_id=echo_id,
            echo_data=echo_data
        )
        
        logger.info(f"Successfully created echo {echo_id}")
        return echo_response
        
    except EchoValidationError as e:
        logger.warning(f"Validation error creating echo: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except EchoServiceError as e:
        logger.error(f"Service error creating echo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error creating echo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create echo"
        )


@router.get(
    "/echoes",
    response_model=EchoListResponse,
    summary="List echoes",
    description="Get a filtered list of user's echoes with advanced filtering options",
    responses={
        200: {"description": "Echoes retrieved successfully"},
        400: {"description": "Invalid query parameters"},
        401: {"description": "Authentication required"},
        500: {"description": "Internal server error"}
    }
)
async def list_echoes(
    emotion: Optional[EmotionType] = Query(None, description="Filter by emotion"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    start_date: Optional[str] = Query(None, description="Start date filter (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date filter (ISO format)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    next_key: Optional[str] = Query(None, description="Pagination key for DynamoDB"),
    current_user: UserContext = Depends(get_current_user)
) -> EchoListResponse:
    """
    List echoes for the authenticated user with advanced filtering
    
    Returns a paginated list of echoes with multiple filtering options.
    Results are sorted by timestamp in descending order (newest first).
    
    Filtering options:
    - emotion: Filter by specific emotion type
    - tags: Comma-separated list of tags (any tag matches)
    - start_date/end_date: Date range filtering (ISO format)
    - page/page_size: Pagination controls
    - next_key: DynamoDB pagination token
    
    Args:
        emotion: Optional emotion filter
        tags: Optional comma-separated tags filter
        start_date: Optional start date filter (ISO format)
        end_date: Optional end date filter (ISO format)
        page: Page number (1-based)
        page_size: Number of items per page (1-100)
        next_key: DynamoDB pagination key
        current_user: Authenticated user context
        
    Returns:
        Paginated list of echoes
    """
    try:
        # Parse optional filters
        tags_list = None
        if tags:
            tags_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
        
        start_date_obj = None
        if start_date:
            try:
                start_date_obj = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid start_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"
                )
        
        end_date_obj = None
        if end_date:
            try:
                end_date_obj = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid end_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"
                )
        
        # Call service with advanced filtering
        response = await echo_service.list_echoes(
            user_id=current_user.user_id,
            emotion=emotion,
            tags=tags_list,
            start_date=start_date_obj,
            end_date=end_date_obj,
            page=page,
            page_size=page_size,
            last_evaluated_key=next_key
        )
        
        logger.info(f"Returned {len(response.echoes)} echoes for user {current_user.user_id}")
        return response
        
    except EchoValidationError as e:
        logger.warning(f"Validation error listing echoes: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except EchoServiceError as e:
        logger.error(f"Service error listing echoes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error listing echoes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list echoes"
        )


@router.get(
    "/echoes/random",
    response_model=EchoResponse,
    summary="Get random echo",
    description="Get a random echo, optionally filtered by emotion",
    responses={
        200: {"description": "Random echo retrieved successfully"},
        404: {"description": "No echoes found"},
        401: {"description": "Authentication required"},
        500: {"description": "Internal server error"}
    }
)
async def get_random_echo(
    emotion: Optional[EmotionType] = Query(None, description="Filter by emotion"),
    current_user: UserContext = Depends(get_current_user)
) -> EchoResponse:
    """
    Get a random echo for the user
    
    Returns a randomly selected echo from the user's collection,
    optionally filtered by emotion.
    
    Args:
        emotion: Optional emotion filter
        current_user: Authenticated user context
        
    Returns:
        Random echo response
        
    Raises:
        HTTPException: If no echoes found
    """
    try:
        response = await echo_service.get_random_echo(
            user_id=current_user.user_id,
            emotion=emotion
        )
        
        logger.info(f"Selected random echo {response.echo_id}")
        return response
        
    except EchoNotFoundError as e:
        logger.info(f"No echoes found for user {current_user.user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except EchoServiceError as e:
        logger.error(f"Service error getting random echo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error getting random echo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get random echo"
        )


@router.get(
    "/echoes/{echo_id}",
    response_model=EchoResponse,
    summary="Get specific echo",
    description="Get a specific echo by ID with optional download URL",
    responses={
        200: {"description": "Echo retrieved successfully"},
        404: {"description": "Echo not found"},
        401: {"description": "Authentication required"},
        500: {"description": "Internal server error"}
    }
)
async def get_echo(
    echo_id: str,
    include_download_url: bool = Query(False, description="Include presigned download URL"),
    current_user: UserContext = Depends(get_current_user)
) -> EchoResponse:
    """
    Get a specific echo by ID
    
    Args:
        echo_id: Echo identifier
        include_download_url: Whether to include presigned download URL
        current_user: Authenticated user context
        
    Returns:
        Echo response
        
    Raises:
        HTTPException: If echo not found
    """
    try:
        response = await echo_service.get_echo(
            user_id=current_user.user_id,
            echo_id=echo_id,
            include_download_url=include_download_url
        )
        
        return response
        
    except EchoNotFoundError as e:
        logger.warning(f"Echo not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except EchoServiceError as e:
        logger.error(f"Service error getting echo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error getting echo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get echo"
        )


@router.delete(
    "/echoes/{echo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete echo",
    description="Delete a specific echo and optionally its associated file",
    responses={
        204: {"description": "Echo deleted successfully"},
        404: {"description": "Echo not found"},
        401: {"description": "Authentication required"},
        500: {"description": "Internal server error"}
    }
)
async def delete_echo(
    echo_id: str,
    delete_file: bool = Query(True, description="Whether to delete the S3 file"),
    current_user: UserContext = Depends(get_current_user)
):
    """
    Delete a specific echo
    
    Args:
        echo_id: Echo identifier
        delete_file: Whether to delete the associated S3 file
        current_user: Authenticated user context
        
    Raises:
        HTTPException: If echo not found or deletion fails
    """
    try:
        success = await echo_service.delete_echo(
            user_id=current_user.user_id,
            echo_id=echo_id,
            delete_file=delete_file
        )
        
        if success:
            logger.info(f"Successfully deleted echo {echo_id}")
        
    except EchoNotFoundError as e:
        logger.warning(f"Echo not found for deletion: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except EchoServiceError as e:
        logger.error(f"Service error deleting echo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error deleting echo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete echo"
        )


@router.get(
    "/echoes/stats",
    summary="Get user echo statistics",
    description="Get comprehensive statistics about user's echoes",
    responses={
        200: {"description": "Statistics retrieved successfully"},
        401: {"description": "Authentication required"},
        500: {"description": "Internal server error"}
    }
)
async def get_user_statistics(
    current_user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get comprehensive statistics about user's echoes
    
    Returns statistics including:
    - Total number of echoes
    - Emotion distribution
    - Total and average duration
    - Date range of echoes
    - Most common emotion
    
    Args:
        current_user: Authenticated user context
        
    Returns:
        Statistics dictionary
    """
    try:
        stats = await echo_service.get_user_statistics(current_user.user_id)
        
        logger.info(f"Retrieved statistics for user {current_user.user_id}")
        return stats
        
    except EchoServiceError as e:
        logger.error(f"Service error getting statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error getting statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get statistics"
        )


# Health check endpoint for monitoring
@router.get(
    "/echoes/health",
    summary="Health check",
    description="Check if the echoes service is healthy",
    include_in_schema=False
)
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "service": "echoes"}