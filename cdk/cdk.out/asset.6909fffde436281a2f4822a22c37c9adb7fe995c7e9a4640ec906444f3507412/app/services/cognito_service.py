"""
Cognito service for user authentication and JWT token validation
"""
import boto3
import logging
import jwt
import requests
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Optional, Dict, Any, List
from functools import lru_cache
import json

from app.core.config import settings
from app.models.user import UserContext, TokenData

logger = logging.getLogger(__name__)


class CognitoService:
    """Service for managing Cognito authentication"""
    
    def __init__(self):
        """Initialize Cognito client"""
        try:
            self.cognito_client = boto3.client(
                'cognito-idp',
                region_name=settings.COGNITO_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            )
            
            self.user_pool_id = settings.COGNITO_USER_POOL_ID
            self.client_id = settings.COGNITO_CLIENT_ID
            self.region = settings.COGNITO_REGION
            
            # Cache for JWT keys
            self._jwks_cache = None
            
            logger.info("Cognito service initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize Cognito service: {e}")
            # Don't raise exception to allow for development without Cognito
            self.cognito_client = None
    
    @lru_cache(maxsize=1)
    def get_jwks(self) -> Dict[str, Any]:
        """
        Get JSON Web Key Set from Cognito
        
        Returns:
            JWKS dictionary
        """
        if not self.user_pool_id:
            raise ValueError("Cognito User Pool ID not configured")
        
        try:
            jwks_url = f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}/.well-known/jwks.json"
            response = requests.get(jwks_url, timeout=10)
            response.raise_for_status()
            
            jwks = response.json()
            logger.debug("Retrieved JWKS from Cognito")
            return jwks
            
        except requests.RequestException as e:
            logger.error(f"Error fetching JWKS: {e}")
            raise
    
    def get_public_key(self, token: str) -> str:
        """
        Get the public key for JWT token verification
        
        Args:
            token: JWT token
            
        Returns:
            Public key for verification
        """
        try:
            # Get token header
            header = jwt.get_unverified_header(token)
            kid = header.get('kid')
            
            if not kid:
                raise ValueError("Token missing 'kid' in header")
            
            # Get JWKS and find matching key
            jwks = self.get_jwks()
            
            for key in jwks.get('keys', []):
                if key.get('kid') == kid:
                    # Convert JWK to PEM format
                    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
                    return public_key
            
            raise ValueError(f"Public key not found for kid: {kid}")
            
        except Exception as e:
            logger.error(f"Error getting public key: {e}")
            raise
    
    def verify_token(self, token: str) -> TokenData:
        """
        Verify JWT token and extract user data
        
        Args:
            token: JWT token to verify
            
        Returns:
            TokenData with user information
            
        Raises:
            ValueError: If token is invalid
        """
        try:
            # For development, allow bypass if Cognito not configured
            if not self.user_pool_id and settings.DEBUG:
                logger.warning("Cognito not configured, using mock token verification")
                return self._mock_token_verification(token)
            
            # Get public key for verification
            public_key = self.get_public_key(token)
            
            # Verify and decode token
            payload = jwt.decode(
                token,
                public_key,
                algorithms=['RS256'],
                audience=self.client_id,
                issuer=f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}"
            )
            
            # Extract token data
            token_data = TokenData(
                sub=payload.get('sub'),
                email=payload.get('email'),
                username=payload.get('cognito:username'),
                exp=payload.get('exp'),
                iat=payload.get('iat'),
                cognito_groups=payload.get('cognito:groups', [])
            )
            
            logger.debug(f"Token verified for user: {token_data.sub}")
            return token_data
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise ValueError(f"Invalid token: {e}")
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            raise ValueError(f"Token verification failed: {e}")
    
    def _mock_token_verification(self, token: str) -> TokenData:
        """
        Mock token verification for development
        
        Args:
            token: JWT token (can be any string in dev mode)
            
        Returns:
            Mock TokenData
        """
        return TokenData(
            sub="dev-user-123",
            email="dev@example.com",
            username="devuser",
            cognito_groups=["users"]
        )
    
    def get_user_context(self, token_data: TokenData) -> UserContext:
        """
        Convert token data to user context
        
        Args:
            token_data: Verified token data
            
        Returns:
            UserContext for the user
        """
        return UserContext(
            user_id=token_data.sub,
            email=token_data.email,
            username=token_data.username,
            cognito_sub=token_data.sub,
            groups=token_data.cognito_groups
        )
    
    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get detailed user information from Cognito
        
        Args:
            access_token: Cognito access token
            
        Returns:
            User information dictionary
        """
        if not self.cognito_client:
            return {"error": "Cognito not configured"}
        
        try:
            response = self.cognito_client.get_user(AccessToken=access_token)
            
            user_info = {
                'username': response.get('Username'),
                'user_attributes': {}
            }
            
            # Parse user attributes
            for attr in response.get('UserAttributes', []):
                user_info['user_attributes'][attr['Name']] = attr['Value']
            
            return user_info
            
        except ClientError as e:
            logger.error(f"Error getting user info: {e}")
            raise ValueError(f"Failed to get user info: {e}")
    
    def validate_user_pool_access(self, user_id: str) -> bool:
        """
        Validate if user has access to the user pool
        
        Args:
            user_id: User identifier
            
        Returns:
            True if user has access
        """
        if not self.cognito_client or settings.DEBUG:
            return True
        
        try:
            # Check if user exists in the user pool
            response = self.cognito_client.admin_get_user(
                UserPoolId=self.user_pool_id,
                Username=user_id
            )
            
            # Check if user is enabled
            user_status = response.get('UserStatus')
            enabled = response.get('Enabled', True)
            
            return user_status == 'CONFIRMED' and enabled
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'UserNotFoundException':
                logger.warning(f"User {user_id} not found in user pool")
                return False
            else:
                logger.error(f"Error validating user pool access: {e}")
                return False
    
    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh access token using refresh token
        
        Args:
            refresh_token: Cognito refresh token
            
        Returns:
            New token set
        """
        if not self.cognito_client:
            raise ValueError("Cognito not configured")
        
        try:
            response = self.cognito_client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow='REFRESH_TOKEN_AUTH',
                AuthParameters={
                    'REFRESH_TOKEN': refresh_token
                }
            )
            
            auth_result = response.get('AuthenticationResult', {})
            
            return {
                'access_token': auth_result.get('AccessToken'),
                'id_token': auth_result.get('IdToken'),
                'token_type': auth_result.get('TokenType', 'Bearer'),
                'expires_in': auth_result.get('ExpiresIn')
            }
            
        except ClientError as e:
            logger.error(f"Error refreshing token: {e}")
            raise ValueError(f"Token refresh failed: {e}")


# Global Cognito service instance
cognito_service = CognitoService()