"""
FastAPI endpoints for Echoes App
Audio upload initialization and echo management
"""

import os
import tempfile
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Header, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from ..services.s3_service import s3_service, UploadRequest, PresignedUrlResponse
from ..services.dynamodb_service import dynamodb_service, EchoMetadata
from ..services.audio_processor import audio_processor
from ..services.auth_service import auth_service, UserInfo, AuthenticationError


# Initialize router
router = APIRouter(prefix="/echoes", tags=["echoes"])
security = HTTPBearer()
logger = logging.getLogger(__name__)


# Request/Response Models
class InitUploadRequest(BaseModel):
    """Request model for upload initialization"""
    content_type: str = Field(..., description="MIME type of the audio file")
    file_size: int = Field(..., gt=0, description="File size in bytes")
    emotion: str = Field(..., min_length=1, description="Emotion tag for the echo")
    tags: Optional[List[str]] = Field(default=[], description="Additional tags")
    location: Optional[Dict[str, float]] = Field(default=None, description="GPS coordinates")


class InitUploadResponse(BaseModel):
    """Response model for upload initialization"""
    upload_url: str
    fields: Dict[str, Any]
    s3_key: str
    expires_at: datetime
    max_file_size: int
    echo_id: str


class CreateEchoRequest(BaseModel):
    """Request model for creating echo metadata"""
    s3_key: str = Field(..., description="S3 key of uploaded audio file")
    emotion: str = Field(..., min_length=1, description="Emotion tag")
    tags: Optional[List[str]] = Field(default=[], description="Additional tags")
    location: Optional[Dict[str, float]] = Field(default=None, description="GPS coordinates")
    transcript: Optional[str] = Field(default="", description="Audio transcript")


class EchoResponse(BaseModel):
    """Response model for echo data"""
    echo_id: str
    emotion: str
    timestamp: str
    playback_url: str
    location: Optional[Dict[str, float]]
    tags: List[str]
    transcript: Optional[str]
    detected_mood: Optional[str]
    audio_duration: float
    created_at: str


class EchoListResponse(BaseModel):
    """Response model for echo list"""
    echoes: List[EchoResponse]
    count: int
    last_evaluated_key: Optional[Dict[str, Any]]


# Dependency functions
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserInfo:
    """
    Get current authenticated user from JWT token
    """
    try:
        token = credentials.credentials
        user_info = auth_service.get_user_info(token)
        return user_info
    except AuthenticationError as e:
        logger.warning(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=401,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )


# API Endpoints
@router.post("/init-upload", response_model=InitUploadResponse)
async def init_upload(
    request: InitUploadRequest,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Initialize audio file upload
    Returns S3 presigned URL for direct client upload
    """
    try:
        logger.info(f"Initializing upload for user {current_user.user_id}")
        
        # Create upload request
        upload_request = UploadRequest(
            user_id=current_user.user_id,
            content_type=request.content_type,
            file_size=request.file_size,
            emotion=request.emotion,
            tags=request.tags or []
        )
        
        # Generate presigned URL
        presigned_response = s3_service.generate_presigned_post(upload_request)
        
        # Extract echo ID from S3 key for response
        echo_id = presigned_response.key.split('/')[-1].split('_')[0]
        
        response = InitUploadResponse(
            upload_url=presigned_response.upload_url,
            fields=presigned_response.fields,
            s3_key=presigned_response.key,
            expires_at=presigned_response.expires_at,
            max_file_size=presigned_response.max_file_size,
            echo_id=echo_id
        )
        
        logger.info(f"Upload initialized successfully for user {current_user.user_id}")
        return response
        
    except ValueError as e:
        logger.warning(f"Invalid upload request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error initializing upload: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize upload")


@router.post("/", response_model=EchoResponse)
async def create_echo(
    request: CreateEchoRequest,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Create echo metadata after successful upload
    """
    try:
        logger.info(f"Creating echo for user {current_user.user_id}")
        
        # Validate S3 key belongs to user
        if not request.s3_key.startswith(f"{current_user.user_id}/"):
            raise HTTPException(status_code=403, detail="Unauthorized access to file")
        
        # Verify file exists in S3
        file_metadata = s3_service.get_file_metadata(request.s3_key, current_user.user_id)
        if not file_metadata:
            raise HTTPException(status_code=404, detail="Audio file not found")
        
        # Extract echo ID from S3 key
        echo_id = request.s3_key.split('/')[-1].split('_')[0]
        
        # Prepare echo data
        echo_data = {
            'user_id': current_user.user_id,
            'echo_id': echo_id,
            'emotion': request.emotion,
            'timestamp': datetime.utcnow().isoformat(),
            's3_url': f"s3://{s3_service.config.bucket_name}/{request.s3_key}",
            's3_key': request.s3_key,
            'location': request.location,
            'tags': request.tags or [],
            'transcript': request.transcript or '',
            'audio_duration': 0.0,  # Will be updated if processing succeeds
            'audio_sample_rate': 0,
            'audio_channels': 0,
            'audio_format': file_metadata.get('content_type', '')
        }
        
        # Create echo in DynamoDB
        echo = dynamodb_service.create_echo(echo_data)
        
        # Generate playback URL
        playback_url = s3_service.generate_presigned_get_url(
            request.s3_key, 
            current_user.user_id
        )
        
        response = EchoResponse(
            echo_id=echo.echo_id,
            emotion=echo.emotion,
            timestamp=echo.timestamp,
            playback_url=playback_url,
            location=echo.location,
            tags=echo.tags,
            transcript=echo.transcript,
            detected_mood=echo.detected_mood,
            audio_duration=echo.audio_duration,
            created_at=echo.created_at
        )
        
        logger.info(f"Echo created successfully: {echo_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating echo: {e}")
        raise HTTPException(status_code=500, detail="Failed to create echo")


@router.get("/", response_model=EchoListResponse)
async def list_echoes(
    emotion: Optional[str] = Query(None, description="Filter by emotion"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of echoes"),
    last_key: Optional[str] = Query(None, description="Last evaluated key for pagination"),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    List user's echoes with optional emotion filtering
    """
    try:
        logger.info(f"Listing echoes for user {current_user.user_id}")
        
        if emotion:
            # Filter by emotion
            echoes = dynamodb_service.filter_echoes_by_emotion(
                current_user.user_id, 
                emotion, 
                limit
            )
            
            echo_responses = []
            for echo in echoes:
                playback_url = s3_service.generate_presigned_get_url(
                    echo.s3_key, 
                    current_user.user_id
                )
                
                echo_responses.append(EchoResponse(
                    echo_id=echo.echo_id,
                    emotion=echo.emotion,
                    timestamp=echo.timestamp,
                    playback_url=playback_url,
                    location=echo.location,
                    tags=echo.tags,
                    transcript=echo.transcript,
                    detected_mood=echo.detected_mood,
                    audio_duration=echo.audio_duration,
                    created_at=echo.created_at
                ))
            
            return EchoListResponse(
                echoes=echo_responses,
                count=len(echo_responses),
                last_evaluated_key=None
            )
        else:
            # List all echoes with pagination
            import json
            last_evaluated_key = None
            if last_key:
                try:
                    last_evaluated_key = json.loads(last_key)
                except json.JSONDecodeError:
                    pass
            
            result = dynamodb_service.list_user_echoes(
                current_user.user_id,
                limit,
                last_evaluated_key
            )
            
            echo_responses = []
            for echo_data in result['echoes']:
                playback_url = s3_service.generate_presigned_get_url(
                    echo_data['s3_key'], 
                    current_user.user_id
                )
                
                echo_responses.append(EchoResponse(
                    echo_id=echo_data['echo_id'],
                    emotion=echo_data['emotion'],
                    timestamp=echo_data['timestamp'],
                    playback_url=playback_url,
                    location=echo_data.get('location'),
                    tags=echo_data.get('tags', []),
                    transcript=echo_data.get('transcript'),
                    detected_mood=echo_data.get('detected_mood'),
                    audio_duration=echo_data.get('audio_duration', 0.0),
                    created_at=echo_data.get('created_at', '')
                ))
            
            return EchoListResponse(
                echoes=echo_responses,
                count=result['count'],
                last_evaluated_key=result['last_evaluated_key']
            )
            
    except Exception as e:
        logger.error(f"Error listing echoes: {e}")
        raise HTTPException(status_code=500, detail="Failed to list echoes")


@router.get("/random", response_model=EchoResponse)
async def get_random_echo(
    emotion: str = Query(..., description="Emotion to match"),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Get a random echo matching the specified emotion
    """
    try:
        logger.info(f"Getting random echo for user {current_user.user_id}, emotion: {emotion}")
        
        # Get random echo
        echo = dynamodb_service.get_random_echo_by_emotion(current_user.user_id, emotion)
        
        if not echo:
            raise HTTPException(status_code=404, detail=f"No echoes found for emotion: {emotion}")
        
        # Generate playback URL
        playback_url = s3_service.generate_presigned_get_url(
            echo.s3_key, 
            current_user.user_id
        )
        
        response = EchoResponse(
            echo_id=echo.echo_id,
            emotion=echo.emotion,
            timestamp=echo.timestamp,
            playback_url=playback_url,
            location=echo.location,
            tags=echo.tags,
            transcript=echo.transcript,
            detected_mood=echo.detected_mood,
            audio_duration=echo.audio_duration,
            created_at=echo.created_at
        )
        
        logger.info(f"Random echo retrieved: {echo.echo_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting random echo: {e}")
        raise HTTPException(status_code=500, detail="Failed to get random echo")


@router.get("/{echo_id}", response_model=EchoResponse)
async def get_echo(
    echo_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Get a specific echo by ID
    """
    try:
        logger.info(f"Getting echo {echo_id} for user {current_user.user_id}")
        
        # Get echo from DynamoDB
        echo = dynamodb_service.get_echo(current_user.user_id, echo_id)
        
        if not echo:
            raise HTTPException(status_code=404, detail="Echo not found")
        
        # Generate playback URL
        playback_url = s3_service.generate_presigned_get_url(
            echo.s3_key, 
            current_user.user_id
        )
        
        response = EchoResponse(
            echo_id=echo.echo_id,
            emotion=echo.emotion,
            timestamp=echo.timestamp,
            playback_url=playback_url,
            location=echo.location,
            tags=echo.tags,
            transcript=echo.transcript,
            detected_mood=echo.detected_mood,
            audio_duration=echo.audio_duration,
            created_at=echo.created_at
        )
        
        logger.info(f"Echo retrieved: {echo_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting echo: {e}")
        raise HTTPException(status_code=500, detail="Failed to get echo")


@router.delete("/{echo_id}")
async def delete_echo(
    echo_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Delete an echo and its associated audio file
    """
    try:
        logger.info(f"Deleting echo {echo_id} for user {current_user.user_id}")
        
        # Get echo details first
        echo = dynamodb_service.get_echo(current_user.user_id, echo_id)
        
        if not echo:
            raise HTTPException(status_code=404, detail="Echo not found")
        
        # Delete from S3
        s3_deleted = s3_service.delete_audio_file(echo.s3_key, current_user.user_id)
        
        # Delete from DynamoDB
        db_deleted = dynamodb_service.delete_echo(current_user.user_id, echo_id)
        
        if not db_deleted:
            logger.warning(f"Failed to delete echo metadata: {echo_id}")
            raise HTTPException(status_code=500, detail="Failed to delete echo metadata")
        
        if not s3_deleted:
            logger.warning(f"Failed to delete audio file: {echo.s3_key}")
        
        logger.info(f"Echo deleted successfully: {echo_id}")
        return {"message": "Echo deleted successfully", "echo_id": echo_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting echo: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete echo")


@router.post("/process-upload")
async def process_uploaded_file(
    file: UploadFile = File(...),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Alternative endpoint for direct file upload and processing
    Used for testing and small files
    """
    try:
        logger.info(f"Processing uploaded file for user {current_user.user_id}")
        
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        try:
            # Process audio file
            result = audio_processor.validate_and_process(
                temp_path, 
                file.content_type or 'audio/webm'
            )
            
            if not result['success']:
                raise HTTPException(status_code=400, detail=result['error'])
            
            # TODO: Upload processed file to S3 and create echo
            # This would be implemented for a complete alternative upload flow
            
            return {
                "message": "File processed successfully",
                "metadata": result['metadata'],
                "processing_applied": result['processing_applied']
            }
            
        finally:
            # Clean up temporary files
            audio_processor.cleanup_temp_file(temp_path)
            if result.get('processed_file'):
                audio_processor.cleanup_temp_file(result['processed_file'])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing uploaded file: {e}")
        raise HTTPException(status_code=500, detail="Failed to process uploaded file")


@router.get("/stats/user")
async def get_user_stats(
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Get user statistics
    """
    try:
        logger.info(f"Getting stats for user {current_user.user_id}")
        
        stats = dynamodb_service.get_user_stats(current_user.user_id)
        
        return {
            "user_id": current_user.user_id,
            "username": current_user.username,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user statistics")