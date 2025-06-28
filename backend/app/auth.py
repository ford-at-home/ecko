"""
JWT Authentication utilities for Echoes API
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging
import uuid

from app.core.config import settings
from app.models.user import UserContext, TokenData

logger = logging.getLogger(__name__)

# Initialize security scheme
security = HTTPBearer()

# Simple in-memory user storage for demo purposes
# In production, this would be replaced with a proper database
DEMO_USERS: Dict[str, Dict[str, Any]] = {}


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token
    
    Args:
        data: Token payload data
        expires_delta: Custom expiration time (optional)
        
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": str(uuid.uuid4())  # JWT ID for token tracking
    })
    
    try:
        encoded_jwt = jwt.encode(
            to_encode, 
            settings.JWT_SECRET_KEY, 
            algorithm=settings.JWT_ALGORITHM
        )
        logger.info(f"Created access token for user: {data.get('sub', 'unknown')}")
        return encoded_jwt
    except Exception as e:
        logger.error(f"Failed to create access token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create access token"
        )


def create_refresh_token(user_id: str) -> str:
    """
    Create a JWT refresh token with longer expiration
    
    Args:
        user_id: User identifier
        
    Returns:
        Encoded JWT refresh token
    """
    data = {
        "sub": user_id,
        "type": "refresh",
        "exp": datetime.utcnow() + timedelta(days=7),  # 7 days for refresh
        "iat": datetime.utcnow(),
        "jti": str(uuid.uuid4())
    }
    
    try:
        refresh_token = jwt.encode(
            data,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        logger.info(f"Created refresh token for user: {user_id}")
        return refresh_token
    except Exception as e:
        logger.error(f"Failed to create refresh token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create refresh token"
        )


def verify_token(token: str) -> TokenData:
    """
    Verify and decode a JWT token
    
    Args:
        token: JWT token string
        
    Returns:
        TokenData object with decoded claims
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        # Extract user ID from subject
        user_id: str = payload.get("sub")
        if user_id is None:
            logger.warning("Token missing subject claim")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create token data object
        token_data = TokenData(
            sub=user_id,
            email=payload.get("email"),
            username=payload.get("username"),
            exp=payload.get("exp"),
            iat=payload.get("iat"),
            cognito_groups=payload.get("cognito_groups", [])
        )
        
        logger.debug(f"Successfully verified token for user: {user_id}")
        return token_data
        
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token verification failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


def refresh_access_token(refresh_token: str) -> str:
    """
    Generate a new access token using a refresh token
    
    Args:
        refresh_token: Valid refresh token
        
    Returns:
        New access token
        
    Raises:
        HTTPException: If refresh token is invalid
    """
    try:
        payload = jwt.decode(
            refresh_token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        # Verify it's a refresh token
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token type"
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token: missing subject"
            )
        
        # Get user data for new access token
        user_data = get_demo_user_by_id(user_id)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Create new access token
        access_token_data = {
            "sub": user_id,
            "email": user_data["email"],
            "username": user_data.get("username"),
            "type": "access"
        }
        
        new_access_token = create_access_token(access_token_data)
        logger.info(f"Refreshed access token for user: {user_id}")
        
        return new_access_token
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserContext:
    """
    Dependency to get current authenticated user from JWT token
    
    Args:
        credentials: HTTP authorization credentials from request
        
    Returns:
        UserContext object for authenticated user
        
    Raises:
        HTTPException: If authentication fails
    """
    token = credentials.credentials
    token_data = verify_token(token)
    
    # Get user data from demo storage
    user_data = get_demo_user_by_id(token_data.sub)
    if not user_data:
        logger.warning(f"User not found for token subject: {token_data.sub}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Create user context
    user_context = UserContext(
        user_id=token_data.sub,
        email=user_data["email"],
        username=user_data.get("username"),
        cognito_sub=user_data.get("cognito_sub"),
        groups=user_data.get("groups", [])
    )
    
    logger.debug(f"Retrieved user context for: {user_context.email}")
    return user_context


def create_demo_user(email: str, username: Optional[str] = None) -> str:
    """
    Create a demo user for authentication testing
    
    Args:
        email: User email address
        username: Optional username
        
    Returns:
        User ID of created user
    """
    user_id = str(uuid.uuid4())
    
    # Store user in demo storage
    DEMO_USERS[user_id] = {
        "user_id": user_id,
        "email": email,
        "username": username or email.split("@")[0],
        "created_at": datetime.utcnow().isoformat(),
        "groups": ["users"],
        "active": True
    }
    
    logger.info(f"Created demo user: {email} with ID: {user_id}")
    return user_id


def get_demo_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Get demo user by email address
    
    Args:
        email: User email address
        
    Returns:
        User data dictionary or None if not found
    """
    for user_data in DEMO_USERS.values():
        if user_data["email"] == email:
            return user_data
    return None


def get_demo_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get demo user by user ID
    
    Args:
        user_id: User identifier
        
    Returns:
        User data dictionary or None if not found
    """
    return DEMO_USERS.get(user_id)


def list_demo_users() -> Dict[str, Dict[str, Any]]:
    """
    Get all demo users (for testing purposes)
    
    Returns:
        Dictionary of all demo users
    """
    return DEMO_USERS.copy()


def authenticate_demo_user(email: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate demo user by email (no password required for demo)
    
    Args:
        email: User email address
        
    Returns:
        User data if authentication successful, None otherwise
    """
    user_data = get_demo_user_by_email(email)
    
    if user_data and user_data.get("active", False):
        logger.info(f"Demo user authenticated: {email}")
        return user_data
    
    logger.warning(f"Demo user authentication failed: {email}")
    return None