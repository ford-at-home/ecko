"""
S3 Service for Echoes App
Handles presigned URL generation and secure audio file uploads
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import uuid

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from pydantic import BaseModel


class S3Config(BaseModel):
    """S3 configuration settings"""
    bucket_name: str
    region: str = "us-east-1"
    presigned_url_expiration: int = 3600  # 1 hour
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    allowed_content_types: list = [
        'audio/webm',
        'audio/wav',
        'audio/mpeg',
        'audio/ogg',
        'audio/x-m4a',
        'audio/mp4'
    ]


class UploadRequest(BaseModel):
    """Request model for upload initialization"""
    user_id: str
    content_type: str
    file_size: int
    emotion: str
    tags: Optional[list] = []


class PresignedUrlResponse(BaseModel):
    """Response model for presigned URL"""
    upload_url: str
    fields: Dict[str, Any]
    key: str
    expires_at: datetime
    max_file_size: int


class S3Service:
    """
    AWS S3 service for handling audio file uploads
    Provides secure presigned URLs for client-side uploads
    """
    
    def __init__(self, config: Optional[S3Config] = None):
        self.config = config or S3Config(
            bucket_name=os.getenv('S3_BUCKET_NAME', 'echoes-audio-dev')
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize S3 client
        try:
            self.s3_client = boto3.client(
                's3',
                region_name=self.config.region,
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
            )
            
            # Test connection (skip in Lambda environment to avoid permission issues)
            try:
                self.s3_client.head_bucket(Bucket=self.config.bucket_name)
                self.logger.info(f"S3 service initialized for bucket: {self.config.bucket_name}")
            except ClientError as e:
                # Log warning but don't fail initialization
                self.logger.warning(f"Could not verify bucket access: {e}")
                self.logger.info(f"S3 service initialized for bucket: {self.config.bucket_name} (unverified)")
            
        except NoCredentialsError:
            self.logger.error("AWS credentials not found")
            raise
        except ClientError as e:
            self.logger.error(f"Error connecting to S3: {e}")
            raise
    
    def generate_s3_key(self, user_id: str, emotion: str) -> str:
        """
        Generate S3 key for audio file
        Format: {user_id}/{emotion}/{echo_id}.webm
        
        Args:
            user_id: User identifier
            emotion: Emotion tag for the echo
        
        Returns:
            S3 object key
        """
        echo_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        return f"{user_id}/{emotion}/{echo_id}_{timestamp}.webm"
    
    def validate_upload_request(self, request: UploadRequest) -> tuple[bool, str]:
        """
        Validate upload request parameters
        
        Args:
            request: Upload request details
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check content type
            if request.content_type not in self.config.allowed_content_types:
                return False, f"Content type {request.content_type} not allowed"
            
            # Check file size
            if request.file_size > self.config.max_file_size:
                return False, f"File size {request.file_size} exceeds limit {self.config.max_file_size}"
            
            if request.file_size <= 0:
                return False, "File size must be greater than 0"
            
            # Validate user ID
            if not request.user_id or len(request.user_id) < 3:
                return False, "Invalid user ID"
            
            # Validate emotion
            if not request.emotion or len(request.emotion.strip()) == 0:
                return False, "Emotion is required"
            
            return True, ""
            
        except Exception as e:
            self.logger.error(f"Error validating upload request: {e}")
            return False, f"Validation error: {str(e)}"
    
    def generate_presigned_post(self, request: UploadRequest) -> PresignedUrlResponse:
        """
        Generate presigned POST URL for direct client upload to S3
        
        Args:
            request: Upload request details
        
        Returns:
            Presigned URL response with upload details
        """
        try:
            # Validate request
            is_valid, error_message = self.validate_upload_request(request)
            if not is_valid:
                raise ValueError(error_message)
            
            # Generate S3 key
            s3_key = self.generate_s3_key(request.user_id, request.emotion)
            
            # Set expiration time
            expires_at = datetime.utcnow() + timedelta(seconds=self.config.presigned_url_expiration)
            
            # Define upload conditions
            conditions = [
                {'bucket': self.config.bucket_name},
                {'key': s3_key},
                {'Content-Type': request.content_type},
                ['content-length-range', 1, self.config.max_file_size],
                {'x-amz-meta-user-id': request.user_id},
                {'x-amz-meta-emotion': request.emotion},
                {'x-amz-meta-upload-timestamp': datetime.utcnow().isoformat()}
            ]
            
            # Add tags if provided
            if request.tags:
                conditions.append({'x-amz-meta-tags': ','.join(request.tags)})
            
            # Generate presigned POST URL
            response = self.s3_client.generate_presigned_post(
                Bucket=self.config.bucket_name,
                Key=s3_key,
                Fields={
                    'Content-Type': request.content_type,
                    'x-amz-meta-user-id': request.user_id,
                    'x-amz-meta-emotion': request.emotion,
                    'x-amz-meta-upload-timestamp': datetime.utcnow().isoformat(),
                    'x-amz-meta-tags': ','.join(request.tags) if request.tags else ''
                },
                Conditions=conditions,
                ExpiresIn=self.config.presigned_url_expiration
            )
            
            self.logger.info(f"Generated presigned URL for user {request.user_id}, key: {s3_key}")
            
            return PresignedUrlResponse(
                upload_url=response['url'],
                fields=response['fields'],
                key=s3_key,
                expires_at=expires_at,
                max_file_size=self.config.max_file_size
            )
            
        except Exception as e:
            self.logger.error(f"Error generating presigned URL: {e}")
            raise
    
    def generate_presigned_get_url(self, s3_key: str, user_id: str, expiration: int = 3600) -> str:
        """
        Generate presigned GET URL for audio file access
        
        Args:
            s3_key: S3 object key
            user_id: User ID for authorization check
            expiration: URL expiration time in seconds
        
        Returns:
            Presigned GET URL
        """
        try:
            # Security check: ensure user can only access their own files
            if not s3_key.startswith(f"{user_id}/"):
                raise ValueError("Unauthorized access to file")
            
            # Generate presigned GET URL
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.config.bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )
            
            self.logger.info(f"Generated presigned GET URL for user {user_id}, key: {s3_key}")
            return url
            
        except Exception as e:
            self.logger.error(f"Error generating presigned GET URL: {e}")
            raise
    
    def delete_audio_file(self, s3_key: str, user_id: str) -> bool:
        """
        Delete audio file from S3
        
        Args:
            s3_key: S3 object key
            user_id: User ID for authorization check
        
        Returns:
            Success status
        """
        try:
            # Security check: ensure user can only delete their own files
            if not s3_key.startswith(f"{user_id}/"):
                raise ValueError("Unauthorized file deletion")
            
            # Delete object
            self.s3_client.delete_object(
                Bucket=self.config.bucket_name,
                Key=s3_key
            )
            
            self.logger.info(f"Deleted audio file for user {user_id}, key: {s3_key}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting audio file: {e}")
            return False
    
    def get_file_metadata(self, s3_key: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for uploaded file
        
        Args:
            s3_key: S3 object key
            user_id: User ID for authorization check
        
        Returns:
            File metadata dict or None if not found
        """
        try:
            # Security check
            if not s3_key.startswith(f"{user_id}/"):
                raise ValueError("Unauthorized file access")
            
            # Get object metadata
            response = self.s3_client.head_object(
                Bucket=self.config.bucket_name,
                Key=s3_key
            )
            
            # Extract metadata
            metadata = {
                'size': response.get('ContentLength', 0),
                'content_type': response.get('ContentType', ''),
                'last_modified': response.get('LastModified'),
                'etag': response.get('ETag', '').strip('"'),
                'user_metadata': response.get('Metadata', {})
            }
            
            self.logger.info(f"Retrieved metadata for user {user_id}, key: {s3_key}")
            return metadata
            
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                self.logger.warning(f"File not found: {s3_key}")
                return None
            else:
                self.logger.error(f"Error getting file metadata: {e}")
                raise
        except Exception as e:
            self.logger.error(f"Error getting file metadata: {e}")
            return None
    
    def list_user_files(self, user_id: str, prefix: str = "", max_keys: int = 100) -> list:
        """
        List audio files for a user
        
        Args:
            user_id: User identifier
            prefix: Additional prefix filter
            max_keys: Maximum number of files to return
        
        Returns:
            List of file information dictionaries
        """
        try:
            # Construct prefix to ensure user can only access their files
            full_prefix = f"{user_id}/"
            if prefix:
                full_prefix += prefix
            
            # List objects
            response = self.s3_client.list_objects_v2(
                Bucket=self.config.bucket_name,
                Prefix=full_prefix,
                MaxKeys=max_keys
            )
            
            files = []
            for obj in response.get('Contents', []):
                files.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'],
                    'etag': obj['ETag'].strip('"')
                })
            
            self.logger.info(f"Listed {len(files)} files for user {user_id}")
            return files
            
        except Exception as e:
            self.logger.error(f"Error listing user files: {e}")
            return []
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on S3 service
        
        Returns:
            Health status information
        """
        try:
            # Try to access bucket
            self.s3_client.head_bucket(Bucket=self.config.bucket_name)
            
            return {
                "status": "healthy",
                "bucket": self.config.bucket_name,
                "region": self.config.region,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"S3 health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }


# Global S3 service instance
s3_service = S3Service()