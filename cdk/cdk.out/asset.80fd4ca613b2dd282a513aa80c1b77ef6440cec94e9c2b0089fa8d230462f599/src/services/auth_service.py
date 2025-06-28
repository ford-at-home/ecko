"""
Authentication Service for Echoes App
Handles AWS Cognito integration and JWT token validation
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import json
import requests

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from jose import JWTError, jwt
from pydantic import BaseModel


class UserInfo(BaseModel):
    """User information model"""
    user_id: str  # Cognito user ID (sub)
    username: str
    email: str
    email_verified: bool = False
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    groups: list = []


class AuthConfig:
    """Authentication configuration"""
    USER_POOL_ID = os.getenv('COGNITO_USER_POOL_ID')
    CLIENT_ID = os.getenv('COGNITO_CLIENT_ID')
    REGION = os.getenv('AWS_REGION', 'us-east-1')
    ALGORITHM = 'RS256'
    
    @property
    def jwks_url(self) -> str:
        return f"https://cognito-idp.{self.REGION}.amazonaws.com/{self.USER_POOL_ID}/.well-known/jwks.json"
    
    @property
    def issuer(self) -> str:
        return f"https://cognito-idp.{self.REGION}.amazonaws.com/{self.USER_POOL_ID}"


class AuthenticationError(Exception):
    """Custom exception for authentication errors"""
    pass


class AuthService:
    """
    AWS Cognito authentication service
    Handles JWT token validation and user information extraction
    """
    
    def __init__(self, config: Optional[AuthConfig] = None):
        self.config = config or AuthConfig()
        self.logger = logging.getLogger(__name__)
        self._jwks_cache = None
        self._jwks_cache_time = None
        
        # Validate configuration
        if not self.config.USER_POOL_ID or not self.config.CLIENT_ID:
            self.logger.error("Cognito configuration missing - USER_POOL_ID and CLIENT_ID required")
            raise ValueError("Cognito configuration incomplete")
        
        # Initialize Cognito client
        try:
            self.cognito_client = boto3.client(
                'cognito-idp',
                region_name=self.config.REGION,
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
            )
            
            self.logger.info(f"Auth service initialized for user pool: {self.config.USER_POOL_ID}")
            
        except NoCredentialsError:
            self.logger.error("AWS credentials not found")
            raise
        except Exception as e:
            self.logger.error(f"Error initializing auth service: {e}")
            raise
    
    def get_jwks(self) -> Dict[str, Any]:
        """
        Get JSON Web Key Set (JWKS) from Cognito
        Implements caching to avoid repeated requests
        
        Returns:
            JWKS dictionary
        """
        try:
            # Check cache (valid for 1 hour)
            current_time = datetime.utcnow().timestamp()
            if (self._jwks_cache and self._jwks_cache_time and 
                current_time - self._jwks_cache_time < 3600):
                return self._jwks_cache
            
            # Fetch JWKS from Cognito
            response = requests.get(self.config.jwks_url, timeout=10)
            response.raise_for_status()
            
            jwks = response.json()
            
            # Update cache
            self._jwks_cache = jwks
            self._jwks_cache_time = current_time
            
            self.logger.debug("JWKS retrieved and cached")
            return jwks
            
        except Exception as e:
            self.logger.error(f"Error retrieving JWKS: {e}")
            raise AuthenticationError(f"Failed to retrieve JWKS: {str(e)}")
    
    def get_signing_key(self, kid: str) -> str:
        """
        Get signing key for JWT verification
        
        Args:
            kid: Key ID from JWT header
        
        Returns:
            RSA public key for verification
        """
        try:
            jwks = self.get_jwks()
            
            # Find the key with matching kid
            for key in jwks.get('keys', []):
                if key.get('kid') == kid:
                    # Convert JWK to PEM format
                    from jose.utils import base64url_decode
                    from cryptography.hazmat.primitives.asymmetric import rsa
                    from cryptography.hazmat.primitives import serialization
                    import base64
                    
                    # Extract RSA components
                    n = base64url_decode(key['n'])
                    e = base64url_decode(key['e'])
                    
                    # Convert to integers
                    n_int = int.from_bytes(n, 'big')
                    e_int = int.from_bytes(e, 'big')
                    
                    # Create RSA public key
                    public_key = rsa.RSAPublicNumbers(e_int, n_int).public_key()
                    
                    # Convert to PEM format
                    pem = public_key.public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    )
                    
                    return pem.decode('utf-8')
            
            raise AuthenticationError(f"Signing key not found for kid: {kid}")
            
        except Exception as e:
            self.logger.error(f"Error getting signing key: {e}")
            raise AuthenticationError(f"Failed to get signing key: {str(e)}")
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate JWT token and extract claims
        
        Args:
            token: JWT token string
        
        Returns:
            Token claims dictionary
        """
        try:
            # Decode header to get key ID
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get('kid')
            
            if not kid:
                raise AuthenticationError("Token missing key ID")
            
            # Get signing key
            signing_key = self.get_signing_key(kid)
            
            # Validate and decode token
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=[self.config.ALGORITHM],
                audience=self.config.CLIENT_ID,
                issuer=self.config.issuer
            )
            
            # Validate token type and usage
            if claims.get('token_use') != 'access':
                raise AuthenticationError("Invalid token usage")
            
            self.logger.debug(f"Token validated for user: {claims.get('sub')}")
            return claims
            
        except JWTError as e:
            self.logger.warning(f"JWT validation error: {e}")
            raise AuthenticationError(f"Invalid token: {str(e)}")
        except Exception as e:
            self.logger.error(f"Token validation error: {e}")
            raise AuthenticationError(f"Token validation failed: {str(e)}")
    
    def get_user_info(self, token: str) -> UserInfo:
        """
        Get user information from validated token
        
        Args:
            token: JWT token string
        
        Returns:
            UserInfo object with user details
        """
        try:
            # Validate token and get claims
            claims = self.validate_token(token)
            
            # Extract user information
            user_info = UserInfo(
                user_id=claims['sub'],
                username=claims.get('username', ''),
                email=claims.get('email', ''),
                email_verified=claims.get('email_verified', False),
                given_name=claims.get('given_name'),
                family_name=claims.get('family_name'),
                groups=claims.get('cognito:groups', [])
            )
            
            self.logger.info(f"User info retrieved for: {user_info.username}")
            return user_info
            
        except Exception as e:
            self.logger.error(f"Error getting user info: {e}")
            raise
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user details from Cognito by user ID
        
        Args:
            user_id: Cognito user ID (sub)
        
        Returns:
            User details dictionary or None if not found
        """
        try:
            # Note: This requires admin privileges
            response = self.cognito_client.admin_get_user(
                UserPoolId=self.config.USER_POOL_ID,
                Username=user_id
            )
            
            # Convert attributes to dictionary
            attributes = {}
            for attr in response.get('UserAttributes', []):
                attributes[attr['Name']] = attr['Value']
            
            user_details = {
                'user_id': user_id,
                'username': response['Username'],
                'user_status': response['UserStatus'],
                'enabled': response['Enabled'],
                'user_create_date': response['UserCreateDate'],
                'user_last_modified_date': response['UserLastModifiedDate'],
                'attributes': attributes
            }
            
            self.logger.info(f"Retrieved user details for: {user_id}")
            return user_details
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'UserNotFoundException':
                self.logger.warning(f"User not found: {user_id}")
                return None
            else:
                self.logger.error(f"Error getting user details: {e}")
                raise
        except Exception as e:
            self.logger.error(f"Error getting user details: {e}")
            return None
    
    def extract_user_id_from_token(self, token: str) -> str:
        """
        Extract user ID from token without full validation
        Used for quick user identification
        
        Args:
            token: JWT token string
        
        Returns:
            User ID (sub claim)
        """
        try:
            # Get unverified claims (for user ID extraction only)
            unverified_claims = jwt.get_unverified_claims(token)
            user_id = unverified_claims.get('sub')
            
            if not user_id:
                raise AuthenticationError("Token missing user ID")
            
            return user_id
            
        except Exception as e:
            self.logger.error(f"Error extracting user ID: {e}")
            raise AuthenticationError(f"Failed to extract user ID: {str(e)}")
    
    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh access token using refresh token
        
        Args:
            refresh_token: Cognito refresh token
        
        Returns:
            New token response
        """
        try:
            response = self.cognito_client.initiate_auth(
                ClientId=self.config.CLIENT_ID,
                AuthFlow='REFRESH_TOKEN_AUTH',
                AuthParameters={
                    'REFRESH_TOKEN': refresh_token
                }
            )
            
            auth_result = response['AuthenticationResult']
            
            self.logger.info("Token refreshed successfully")
            return {
                'access_token': auth_result['AccessToken'],
                'token_type': auth_result['TokenType'],
                'expires_in': auth_result['ExpiresIn'],
                'id_token': auth_result.get('IdToken')
            }
            
        except ClientError as e:
            self.logger.error(f"Error refreshing token: {e}")
            raise AuthenticationError(f"Token refresh failed: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error refreshing token: {e}")
            raise AuthenticationError(f"Token refresh error: {str(e)}")
    
    def sign_out_user(self, access_token: str) -> bool:
        """
        Sign out user globally
        
        Args:
            access_token: User's access token
        
        Returns:
            Success status
        """
        try:
            self.cognito_client.global_sign_out(
                AccessToken=access_token
            )
            
            self.logger.info("User signed out successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error signing out user: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on auth service
        
        Returns:
            Health status information
        """
        try:
            # Try to get JWKS
            jwks = self.get_jwks()
            
            return {
                "status": "healthy",
                "user_pool_id": self.config.USER_POOL_ID,
                "region": self.config.REGION,
                "jwks_keys_count": len(jwks.get('keys', [])),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Auth service health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }


# Global auth service instance
auth_service = AuthService()