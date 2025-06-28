"""
User authentication and context models
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Dict, Any, List
from datetime import datetime


class UserContext(BaseModel):
    """User context from authentication"""
    user_id: str = Field(..., description="Unique user identifier")
    email: Optional[EmailStr] = Field(None, description="User email address")
    username: Optional[str] = Field(None, description="Username")
    cognito_sub: Optional[str] = Field(None, description="Cognito user sub")
    groups: List[str] = Field(default_factory=list, description="User groups")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "abc123",
                "email": "user@example.com",
                "username": "johndoe",
                "cognito_sub": "cognito-sub-123",
                "groups": ["users"]
            }
        }


class TokenData(BaseModel):
    """JWT token data"""
    sub: str = Field(..., description="Subject (user ID)")
    email: Optional[str] = Field(None, description="User email")
    username: Optional[str] = Field(None, description="Username")
    exp: Optional[int] = Field(None, description="Expiration timestamp")
    iat: Optional[int] = Field(None, description="Issued at timestamp")
    cognito_groups: List[str] = Field(default_factory=list, description="Cognito groups")


class AuthResponse(BaseModel):
    """Authentication response"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    user: UserContext = Field(..., description="User information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 86400,
                "user": {
                    "user_id": "abc123",
                    "email": "user@example.com",
                    "username": "johndoe"
                }
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "validation_error",
                "message": "Invalid input data",
                "details": {"field": "emotion", "issue": "required field missing"},
                "timestamp": "2025-06-25T15:00:00Z"
            }
        }


class SuccessResponse(BaseModel):
    """Standard success response"""
    success: bool = Field(default=True, description="Success status")
    message: str = Field(..., description="Success message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {},
                "timestamp": "2025-06-25T15:00:00Z"
            }
        }