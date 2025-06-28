"""
Pydantic schemas for API request/response validation
"""
from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


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
    """Location information schema"""
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lng: float = Field(..., ge=-180, le=180, description="Longitude")
    address: Optional[str] = Field(None, max_length=500, description="Human-readable address")
    
    class Config:
        json_schema_extra = {
            "example": {
                "lat": 37.5407,
                "lng": -77.4360,
                "address": "Richmond, VA, USA"
            }
        }


# User Schemas
class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr = Field(..., description="Email address")
    name: str = Field(..., min_length=1, max_length=255, description="Full name")


class UserCreate(UserBase):
    """Schema for creating a new user"""
    pass


class UserUpdate(BaseModel):
    """Schema for updating user information"""
    email: Optional[EmailStr] = Field(None, description="Email address")
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Full name")


class UserResponse(UserBase):
    """Schema for user response"""
    id: str = Field(..., description="User ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    is_active: str = Field(..., description="Active status")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "abc123",
                "email": "user@example.com",
                "name": "John Doe",
                "created_at": "2025-06-25T15:00:00Z",
                "updated_at": "2025-06-25T15:00:00Z",
                "is_active": "true"
            }
        }


# Echo Schemas
class EchoBase(BaseModel):
    """Base echo schema"""
    emotion: EmotionType = Field(..., description="Primary emotion of the echo")
    caption: Optional[str] = Field(None, max_length=1000, description="User caption")
    location_lat: Optional[float] = Field(None, ge=-90, le=90, description="Latitude")
    location_lng: Optional[float] = Field(None, ge=-180, le=180, description="Longitude")
    location_address: Optional[str] = Field(None, max_length=500, description="Location address")
    duration: Optional[float] = Field(None, ge=0.1, le=300, description="Duration in seconds")
    transcript: Optional[str] = Field(None, max_length=1000, description="Audio transcription")
    detected_mood: Optional[str] = Field(None, max_length=50, description="AI-detected mood")
    tags: Optional[List[str]] = Field(default_factory=list, max_items=10, description="Tags")
    
    @validator('tags')
    def validate_tags(cls, v):
        """Validate and clean tags"""
        if not v:
            return []
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
    """Schema for creating a new echo"""
    s3_url: str = Field(..., description="S3 URL for audio file")
    s3_key: Optional[str] = Field(None, description="S3 key for audio file")
    file_size: Optional[int] = Field(None, ge=0, description="File size in bytes")
    
    class Config:
        json_schema_extra = {
            "example": {
                "emotion": "joy",
                "caption": "Kids playing by the river",
                "s3_url": "s3://echoes-audio/abc123/uuid-1234.webm",
                "s3_key": "abc123/uuid-1234.webm",
                "location_lat": 37.5407,
                "location_lng": -77.4360,
                "location_address": "James River, Richmond, VA",
                "duration": 25.5,
                "transcript": "Rio laughing and water splashing",
                "detected_mood": "joyful",
                "tags": ["river", "kids", "outdoors"],
                "file_size": 1024000
            }
        }


class EchoUpdate(BaseModel):
    """Schema for updating an echo"""
    emotion: Optional[EmotionType] = Field(None, description="Primary emotion")
    caption: Optional[str] = Field(None, max_length=1000, description="User caption")
    location_lat: Optional[float] = Field(None, ge=-90, le=90, description="Latitude")
    location_lng: Optional[float] = Field(None, ge=-180, le=180, description="Longitude")
    location_address: Optional[str] = Field(None, max_length=500, description="Location address")
    transcript: Optional[str] = Field(None, max_length=1000, description="Audio transcription")
    detected_mood: Optional[str] = Field(None, max_length=50, description="AI-detected mood")
    tags: Optional[List[str]] = Field(None, max_items=10, description="Tags")
    
    @validator('tags')
    def validate_tags(cls, v):
        """Validate and clean tags"""
        if v is None:
            return v
        return EchoBase.__validators__['validate_tags'](cls, v)


class EchoResponse(EchoBase):
    """Schema for echo response"""
    id: str = Field(..., description="Echo ID")
    user_id: str = Field(..., description="User ID")
    s3_url: str = Field(..., description="S3 URL for audio file")
    s3_key: Optional[str] = Field(None, description="S3 key for audio file")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    # Computed properties
    location: Optional[LocationData] = Field(None, description="Location data")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "uuid-1234-5678-9abc",
                "user_id": "abc123",
                "emotion": "joy",
                "caption": "Kids playing by the river",
                "s3_url": "s3://echoes-audio/abc123/uuid-1234.webm",
                "s3_key": "abc123/uuid-1234.webm",
                "location_lat": 37.5407,
                "location_lng": -77.4360,
                "location_address": "James River, Richmond, VA",
                "duration": 25.5,
                "transcript": "Rio laughing and water splashing",
                "detected_mood": "joyful",
                "tags": ["river", "kids", "outdoors"],
                "file_size": 1024000,
                "created_at": "2025-06-25T15:00:00Z",
                "updated_at": "2025-06-25T15:00:00Z",
                "location": {
                    "lat": 37.5407,
                    "lng": -77.4360,
                    "address": "James River, Richmond, VA"
                }
            }
        }


class EchoListResponse(BaseModel):
    """Schema for echo list response"""
    echoes: List[EchoResponse]
    total_count: int
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
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


# Utility Schemas
class PresignedUrlRequest(BaseModel):
    """Schema for presigned URL request"""
    file_extension: str = Field(..., regex=r'^(webm|wav|mp3|m4a|ogg)$', description="File extension")
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


class PresignedUrlResponse(BaseModel):
    """Schema for presigned URL response"""
    upload_url: str = Field(..., description="Presigned URL for uploading")
    echo_id: str = Field(..., description="Generated echo ID")
    s3_key: str = Field(..., description="S3 key for the file")
    expires_in: int = Field(..., description="URL expiration time in seconds")


# Standard Response Schemas
class ErrorResponse(BaseModel):
    """Standard error response schema"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


class SuccessResponse(BaseModel):
    """Standard success response schema"""
    success: bool = Field(default=True, description="Success status")
    message: str = Field(..., description="Success message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")