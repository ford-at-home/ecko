"""
Authentication router for Echoes API
Handles user authentication, token management, and demo user operations
"""
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime

from app.auth import (
    create_access_token,
    create_refresh_token,
    refresh_access_token,
    authenticate_demo_user,
    create_demo_user,
    get_demo_user_by_email,
    list_demo_users,
    get_current_user,
    security
)
from app.models.user import AuthResponse, UserContext, ErrorResponse

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()


# Request/Response models
class LoginRequest(BaseModel):
    """Demo login request (email only)"""
    email: EmailStr = Field(..., description="User email address")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "demo@example.com"
            }
        }


class CreateUserRequest(BaseModel):
    """Create demo user request"""
    email: EmailStr = Field(..., description="User email address")
    username: Optional[str] = Field(None, description="Username (optional)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "newuser@example.com",
                "username": "newuser"
            }
        }


class RefreshTokenRequest(BaseModel):
    """Token refresh request"""
    refresh_token: str = Field(..., description="Valid refresh token")
    
    class Config:
        json_schema_extra = {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }


class TokenResponse(BaseModel):
    """Token refresh response"""
    access_token: str = Field(..., description="New access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 86400
            }
        }


class UserListResponse(BaseModel):
    """Demo users list response"""
    users: List[Dict[str, Any]] = Field(..., description="List of demo users")
    total: int = Field(..., description="Total number of users")
    
    class Config:
        json_schema_extra = {
            "example": {
                "users": [
                    {
                        "user_id": "abc123",
                        "email": "demo@example.com",
                        "username": "demo",
                        "created_at": "2024-01-01T00:00:00",
                        "active": True
                    }
                ],
                "total": 1
            }
        }


@router.post("/login", response_model=AuthResponse, status_code=status.HTTP_200_OK)
async def demo_login(login_request: LoginRequest):
    """
    Demo user login (email only, no password required)
    
    This is a simplified authentication for demo purposes.
    In production, you would validate proper credentials.
    """
    try:
        # Authenticate demo user
        user_data = authenticate_demo_user(login_request.email)
        
        if not user_data:
            logger.warning(f"Demo login failed for: {login_request.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed. User not found or inactive."
            )
        
        # Create tokens
        access_token_data = {
            "sub": user_data["user_id"],
            "email": user_data["email"],
            "username": user_data.get("username"),
            "type": "access"
        }
        
        access_token = create_access_token(access_token_data)
        refresh_token = create_refresh_token(user_data["user_id"])
        
        # Create user context
        user_context = UserContext(
            user_id=user_data["user_id"],
            email=user_data["email"],
            username=user_data.get("username"),
            groups=user_data.get("groups", [])
        )
        
        logger.info(f"Demo login successful for: {login_request.email}")
        
        return AuthResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=86400,  # 24 hours in seconds
            user=user_context
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Demo login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )


@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def refresh_token(refresh_request: RefreshTokenRequest):
    """
    Refresh access token using refresh token
    """
    try:
        new_access_token = refresh_access_token(refresh_request.refresh_token)
        
        logger.info("Token refresh successful")
        
        return TokenResponse(
            access_token=new_access_token,
            token_type="bearer",
            expires_in=86400  # 24 hours in seconds
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh service error"
        )


@router.post("/users/create", response_model=UserContext, status_code=status.HTTP_201_CREATED)
async def create_demo_user_endpoint(user_request: CreateUserRequest):
    """
    Create a new demo user
    
    This endpoint creates demo users for testing purposes.
    In production, this would be replaced with proper user registration.
    """
    try:
        # Check if user already exists
        existing_user = get_demo_user_by_email(user_request.email)
        if existing_user:
            logger.warning(f"Demo user creation failed - user exists: {user_request.email}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email already exists"
            )
        
        # Create new demo user
        user_id = create_demo_user(
            email=user_request.email,
            username=user_request.username
        )
        
        # Get created user data
        user_data = get_demo_user_by_email(user_request.email)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve created user"
            )
        
        logger.info(f"Demo user created successfully: {user_request.email}")
        
        return UserContext(
            user_id=user_data["user_id"],
            email=user_data["email"],
            username=user_data.get("username"),
            groups=user_data.get("groups", [])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Demo user creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User creation service error"
        )


@router.get("/me", response_model=UserContext, status_code=status.HTTP_200_OK)
async def get_current_user_info(current_user: UserContext = Depends(get_current_user)):
    """
    Get current authenticated user information
    
    This is a protected endpoint that requires valid JWT token.
    """
    logger.info(f"User info requested for: {current_user.email}")
    return current_user


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(current_user: UserContext = Depends(get_current_user)):
    """
    Logout current user
    
    In a production system, this would invalidate the token.
    For this demo, we just acknowledge the logout request.
    """
    logger.info(f"User logout: {current_user.email}")
    
    return {
        "message": "Logout successful",
        "user_id": current_user.user_id,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/users", response_model=UserListResponse, status_code=status.HTTP_200_OK)
async def list_demo_users_endpoint():
    """
    List all demo users (for development/testing purposes)
    
    This endpoint is for demo purposes only.
    In production, this would be protected and limited to admin users.
    """
    try:
        users_data = list_demo_users()
        
        # Convert to list format
        users_list = []
        for user_data in users_data.values():
            users_list.append({
                "user_id": user_data["user_id"],
                "email": user_data["email"],
                "username": user_data.get("username"),
                "created_at": user_data.get("created_at"),
                "groups": user_data.get("groups", []),
                "active": user_data.get("active", True)
            })
        
        logger.info(f"Demo users list requested - {len(users_list)} users")
        
        return UserListResponse(
            users=users_list,
            total=len(users_list)
        )
        
    except Exception as e:
        logger.error(f"List demo users error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users list"
        )


@router.get("/health", status_code=status.HTTP_200_OK)
async def auth_health_check():
    """
    Authentication service health check
    """
    return {
        "service": "auth",
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "demo_users_count": len(list_demo_users())
    }