"""
Echoes API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List
import logging
from datetime import datetime
import uuid
import os

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
from app.services.s3_service import s3_service
from app.services.dynamodb_service import dynamodb_service
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
    "/echoes/upload-url",
    response_model=PresignedUrlResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate presigned upload URL",
    description="Generate a secure presigned URL for direct S3 audio upload with enhanced validation"
)
async def generate_upload_url(
    request: PresignedUrlRequest,
    current_user: UserContext = Depends(get_current_user)
) -> PresignedUrlResponse:
    """
    Generate secure presigned URL for audio file upload
    
    This endpoint generates a secure presigned S3 URL with enhanced validation
    and user/timestamp-based key structure for direct client uploads.
    
    Args:
        request: Upload request with file details
        current_user: Authenticated user context
        
    Returns:
        Presigned URL response with upload details and security metadata
        
    Raises:
        HTTPException: If validation fails or S3 operation fails
    """
    try:
        logger.info(f"Generating secure presigned URL for user {current_user.user_id}")
        
        # Enhanced S3 service with validation
        import sys
        sys.path.append('/Users/williamprior/Development/GitHub/ecko')
        from backend.services.s3 import create_s3_service
        enhanced_s3 = create_s3_service(
            bucket_name=settings.S3_BUCKET_NAME,
            region=settings.AWS_REGION,
            aws_profile=os.getenv('AWS_PROFILE')  # Use personal AWS profile
        )
        
        # Generate secure presigned URL with timestamp structure
        upload_data = enhanced_s3.generate_presigned_upload_url(
            user_id=current_user.user_id,
            file_extension=request.file_extension,
            content_type=request.content_type,
            expires_in=settings.S3_PRESIGNED_URL_EXPIRATION
        )
        
        logger.info(f"Generated secure presigned URL for echo {upload_data['echo_id']}")
        
        return PresignedUrlResponse(
            upload_url=upload_data['upload_url'],
            echo_id=upload_data['echo_id'],
            s3_key=upload_data['s3_key'],
            expires_in=upload_data['expires_in']
        )
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error generating presigned URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate upload URL: {str(e)}"
        )


@router.post(
    "/echoes/init-upload",
    response_model=PresignedUrlResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initialize audio upload (legacy)",
    description="Legacy endpoint - use /echoes/upload-url instead"
)
async def init_upload(
    request: PresignedUrlRequest,
    current_user: UserContext = Depends(get_current_user)
) -> PresignedUrlResponse:
    """
    Generate presigned URL for audio file upload (legacy endpoint)
    
    This is a legacy endpoint. New implementations should use /echoes/upload-url
    which provides enhanced security and validation.
    
    Args:
        request: Upload request with file details
        current_user: Authenticated user context
        
    Returns:
        Presigned URL response with upload details
        
    Raises:
        HTTPException: If S3 operation fails
    """
    # Redirect to new endpoint for consistency
    return await generate_upload_url(request, current_user)


@router.post(
    "/echoes",
    response_model=EchoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new echo",
    description="Save echo metadata after successful audio upload"
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
        logger.info(f"Creating echo {echo_id} for user {current_user.user_id}")
        
        # Generate S3 key and URL
        s3_key = settings.get_s3_key(current_user.user_id, echo_id, echo_data.file_extension)
        s3_url = settings.get_s3_url(s3_key)
        
        # Verify the file exists in S3 (optional check)
        if not s3_service.check_file_exists(s3_key):
            logger.warning(f"Audio file not found in S3: {s3_key}")
            # Note: We'll still create the echo as the upload might be in progress
        
        # Create Echo instance
        echo = Echo(
            echo_id=echo_id,
            user_id=current_user.user_id,
            timestamp=datetime.utcnow(),
            s3_url=s3_url,
            s3_key=s3_key,
            emotion=echo_data.emotion,
            tags=echo_data.tags,
            transcript=echo_data.transcript,
            detected_mood=echo_data.detected_mood,
            location=echo_data.location,
            duration_seconds=echo_data.duration_seconds,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Get file metadata from S3 if available
        file_metadata = s3_service.get_file_metadata(s3_key)
        if file_metadata:
            echo.file_size = file_metadata.get('size')
        
        # Save to DynamoDB
        created_echo = dynamodb_service.create_echo(echo)
        
        logger.info(f"Successfully created echo {echo_id}")
        
        # Convert to response model
        return EchoResponse(
            echo_id=created_echo.echo_id,
            emotion=created_echo.emotion,
            timestamp=created_echo.timestamp,
            s3_url=created_echo.s3_url,
            location=created_echo.location,
            tags=created_echo.tags,
            transcript=created_echo.transcript,
            detected_mood=created_echo.detected_mood,
            duration_seconds=created_echo.duration_seconds,
            created_at=created_echo.created_at
        )
        
    except ValueError as e:
        logger.error(f"Validation error creating echo: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating echo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create echo: {str(e)}"
        )


@router.get(
    "/echoes",
    response_model=EchoListResponse,
    summary="List echoes",
    description="Get a filtered list of user's echoes"
)
async def list_echoes(
    emotion: Optional[EmotionType] = Query(None, description="Filter by emotion"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: UserContext = Depends(get_current_user)
) -> EchoListResponse:
    """
    List echoes for the authenticated user
    
    Returns a paginated list of echoes, optionally filtered by emotion.
    Results are sorted by timestamp in descending order (newest first).
    
    Args:
        emotion: Optional emotion filter
        page: Page number (1-based)
        page_size: Number of items per page (1-100)
        current_user: Authenticated user context
        
    Returns:
        Paginated list of echoes
    """
    try:
        logger.info(f"Listing echoes for user {current_user.user_id}, emotion={emotion}")
        
        # Calculate pagination offset
        # Note: DynamoDB uses different pagination, so we'll implement simple pagination
        offset = (page - 1) * page_size
        
        # Get echoes from DynamoDB
        echoes, next_key = dynamodb_service.list_echoes(
            user_id=current_user.user_id,
            emotion=emotion,
            limit=page_size * 2,  # Get extra to handle pagination
            last_evaluated_key=None
        )
        
        # Apply manual pagination for now (in production, use proper DynamoDB pagination)
        if offset >= len(echoes):
            paginated_echoes = []
        else:
            paginated_echoes = echoes[offset:offset + page_size]
        
        # Convert to response models
        echo_responses = [
            EchoResponse(
                echo_id=echo.echo_id,
                emotion=echo.emotion,
                timestamp=echo.timestamp,
                s3_url=echo.s3_url,
                location=echo.location,
                tags=echo.tags,
                transcript=echo.transcript,
                detected_mood=echo.detected_mood,
                duration_seconds=echo.duration_seconds,
                created_at=echo.created_at
            )
            for echo in paginated_echoes
        ]
        
        has_more = len(echoes) > offset + page_size
        
        response = EchoListResponse(
            echoes=echo_responses,
            total_count=len(echoes),  # Approximate count
            page=page,
            page_size=page_size,
            has_more=has_more
        )
        
        logger.info(f"Returned {len(echo_responses)} echoes")
        return response
        
    except Exception as e:
        logger.error(f"Error listing echoes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list echoes: {str(e)}"
        )


@router.get(
    "/echoes/random",
    response_model=EchoResponse,
    summary="Get random echo",
    description="Get a random echo, optionally filtered by emotion"
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
        logger.info(f"Getting random echo for user {current_user.user_id}, emotion={emotion}")
        
        random_echo = dynamodb_service.get_random_echo(
            user_id=current_user.user_id,
            emotion=emotion
        )
        
        if not random_echo:
            logger.info(f"No echoes found for user {current_user.user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No echoes found"
            )
        
        logger.info(f"Selected random echo {random_echo.echo_id}")
        
        return EchoResponse(
            echo_id=random_echo.echo_id,
            emotion=random_echo.emotion,
            timestamp=random_echo.timestamp,
            s3_url=random_echo.s3_url,
            location=random_echo.location,
            tags=random_echo.tags,
            transcript=random_echo.transcript,
            detected_mood=random_echo.detected_mood,
            duration_seconds=random_echo.duration_seconds,
            created_at=random_echo.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting random echo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get random echo: {str(e)}"
        )


@router.get(
    "/echoes/{echo_id}",
    response_model=EchoResponse,
    summary="Get specific echo",
    description="Get a specific echo by ID"
)
async def get_echo(
    echo_id: str,
    current_user: UserContext = Depends(get_current_user)
) -> EchoResponse:
    """
    Get a specific echo by ID
    
    Args:
        echo_id: Echo identifier
        current_user: Authenticated user context
        
    Returns:
        Echo response
        
    Raises:
        HTTPException: If echo not found
    """
    try:
        logger.info(f"Getting echo {echo_id} for user {current_user.user_id}")
        
        echo = dynamodb_service.get_echo(
            user_id=current_user.user_id,
            echo_id=echo_id
        )
        
        if not echo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Echo not found"
            )
        
        return EchoResponse(
            echo_id=echo.echo_id,
            emotion=echo.emotion,
            timestamp=echo.timestamp,
            s3_url=echo.s3_url,
            location=echo.location,
            tags=echo.tags,
            transcript=echo.transcript,
            detected_mood=echo.detected_mood,
            duration_seconds=echo.duration_seconds,
            created_at=echo.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting echo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get echo: {str(e)}"
        )


@router.delete(
    "/echoes/{echo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete echo",
    description="Delete a specific echo"
)
async def delete_echo(
    echo_id: str,
    current_user: UserContext = Depends(get_current_user)
):
    """
    Delete a specific echo
    
    Args:
        echo_id: Echo identifier
        current_user: Authenticated user context
        
    Raises:
        HTTPException: If echo not found or deletion fails
    """
    try:
        logger.info(f"Deleting echo {echo_id} for user {current_user.user_id}")
        
        # First get the echo to get S3 key
        echo = dynamodb_service.get_echo(
            user_id=current_user.user_id,
            echo_id=echo_id
        )
        
        if not echo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Echo not found"
            )
        
        # Delete from DynamoDB
        success = dynamodb_service.delete_echo(
            user_id=current_user.user_id,
            echo_id=echo_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Echo not found"
            )
        
        # Delete from S3 (optional - could be done asynchronously)
        try:
            s3_service.delete_file(echo.s3_key)
            logger.info(f"Deleted S3 file: {echo.s3_key}")
        except Exception as e:
            logger.warning(f"Failed to delete S3 file {echo.s3_key}: {e}")
        
        logger.info(f"Successfully deleted echo {echo_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting echo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete echo: {str(e)}"
        )