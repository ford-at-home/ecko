"""
Echo data models and schemas
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class EmotionType(str, Enum):
    """Predefined emotion types"""
    JOY = "joy"
    CALM = "calm"
    SADNESS = "sadness"
    ANGER = "anger"
    FEAR = "fear"
    SURPRISE = "surprise"
    LOVE = "love"
    NOSTALGIA = "nostalgia"
    EXCITEMENT = "excitement"
    PEACEFUL = "peaceful"
    MELANCHOLY = "melancholy"
    HOPE = "hope"


class LocationData(BaseModel):
    """Location information for an echo"""
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lng: float = Field(..., ge=-180, le=180, description="Longitude")
    address: Optional[str] = Field(None, max_length=200, description="Human-readable address")
    
    class Config:
        json_schema_extra = {
            "example": {
                "lat": 37.5407,
                "lng": -77.4360,
                "address": "Richmond, VA, USA"
            }
        }


class EchoBase(BaseModel):
    """Base echo model with common fields"""
    emotion: EmotionType = Field(..., description="Primary emotion of the echo")
    tags: List[str] = Field(default_factory=list, max_items=10, description="User-defined tags")
    transcript: Optional[str] = Field(None, max_length=1000, description="Audio transcription")
    detected_mood: Optional[str] = Field(None, max_length=50, description="AI-detected mood")
    location: Optional[LocationData] = Field(None, description="Location where echo was recorded")
    
    @validator('tags')
    def validate_tags(cls, v):
        if not isinstance(v, list):
            raise ValueError('tags must be a list')
        # Clean and validate tags
        cleaned_tags = []
        for tag in v:
            if isinstance(tag, str) and tag.strip():
                cleaned_tag = tag.strip().lower()[:50]  # Max 50 chars per tag
                if cleaned_tag not in cleaned_tags:
                    cleaned_tags.append(cleaned_tag)
        return cleaned_tags[:10]  # Max 10 tags


class EchoCreate(EchoBase):
    """Model for creating a new echo"""
    file_extension: str = Field(..., pattern=r'^(webm|wav|mp3|m4a|ogg)$', description="Audio file extension")
    duration_seconds: Optional[float] = Field(None, ge=0.1, le=300, description="Audio duration in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "emotion": "joy",
                "tags": ["river", "kids", "outdoors"],
                "transcript": "Rio laughing and water splashing",
                "detected_mood": "joyful",
                "file_extension": "webm",
                "duration_seconds": 25.5,
                "location": {
                    "lat": 37.5407,
                    "lng": -77.4360,
                    "address": "James River, Richmond, VA"
                }
            }
        }


class Echo(EchoBase):
    """Complete echo model with all fields"""
    echo_id: str = Field(..., description="Unique echo identifier")
    user_id: str = Field(..., description="User identifier")
    timestamp: datetime = Field(..., description="When the echo was created")
    s3_url: str = Field(..., description="S3 URL for the audio file")
    s3_key: str = Field(..., description="S3 key for the audio file")
    duration_seconds: Optional[float] = Field(None, ge=0.1, le=300, description="Audio duration in seconds")
    file_size: Optional[int] = Field(None, ge=0, description="File size in bytes")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Record update timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "echo_id": "uuid-1234-5678-9abc",
                "user_id": "abc123",
                "emotion": "calm",
                "timestamp": "2025-06-25T15:00:00Z",
                "s3_url": "s3://echoes-audio/abc123/uuid-1234.webm",
                "s3_key": "abc123/uuid-1234.webm",
                "location": {
                    "lat": 37.5407,
                    "lng": -77.4360
                },
                "tags": ["river", "kids", "outdoors"],
                "transcript": "Rio laughing and water splashing",
                "detected_mood": "joy",
                "duration_seconds": 25.5,
                "file_size": 1024000,
                "created_at": "2025-06-25T15:00:00Z",
                "updated_at": "2025-06-25T15:00:00Z"
            }
        }


class EchoResponse(BaseModel):
    """Response model for echo API calls"""
    echo_id: str
    emotion: EmotionType
    timestamp: datetime
    s3_url: str
    location: Optional[LocationData]
    tags: List[str]
    transcript: Optional[str]
    detected_mood: Optional[str]
    duration_seconds: Optional[float]
    created_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "echo_id": "uuid-1234-5678-9abc",
                "emotion": "joy",
                "timestamp": "2025-06-25T15:00:00Z",
                "s3_url": "s3://echoes-audio/abc123/uuid-1234.webm",
                "location": {
                    "lat": 37.5407,
                    "lng": -77.4360,
                    "address": "James River, Richmond, VA"
                },
                "tags": ["river", "kids", "outdoors"],
                "transcript": "Rio laughing and water splashing",
                "detected_mood": "joyful",
                "duration_seconds": 25.5,
                "created_at": "2025-06-25T15:00:00Z"
            }
        }


class EchoListResponse(BaseModel):
    """Response model for echo list API calls"""
    echoes: List[EchoResponse]
    total_count: int
    page: int = 1
    page_size: int = 20
    has_more: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "echoes": [],
                "total_count": 0,
                "page": 1,
                "page_size": 20,
                "has_more": False
            }
        }


class PresignedUrlRequest(BaseModel):
    """Request model for presigned URL generation"""
    file_extension: str = Field(..., pattern=r'^(webm|wav|mp3|m4a|ogg)$', description="File extension")
    content_type: str = Field(..., description="MIME type of the file")
    
    @validator('content_type')
    def validate_content_type(cls, v, values):
        """Validate content type matches file extension"""
        extension = values.get('file_extension', '').lower()
        valid_types = {
            'webm': 'audio/webm',
            'wav': 'audio/wav',
            'mp3': 'audio/mpeg',
            'm4a': 'audio/mp4',
            'ogg': 'audio/ogg'
        }
        
        if extension in valid_types and v != valid_types[extension]:
            raise ValueError(f'Content type {v} does not match file extension {extension}')
        
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_extension": "webm",
                "content_type": "audio/webm"
            }
        }


class PresignedUrlResponse(BaseModel):
    """Response model for presigned URL"""
    upload_url: str = Field(..., description="Presigned URL for uploading")
    echo_id: str = Field(..., description="Generated echo ID")
    s3_key: str = Field(..., description="S3 key for the file")
    expires_in: int = Field(..., description="URL expiration time in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "upload_url": "https://echoes-audio.s3.amazonaws.com/abc123/uuid-1234.webm?X-Amz-Algorithm=...",
                "echo_id": "uuid-1234-5678-9abc",
                "s3_key": "abc123/uuid-1234.webm",
                "expires_in": 3600
            }
        }