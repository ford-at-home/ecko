"""
S3 service for audio file storage and presigned URL generation
"""
import boto3
import logging
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Optional, Dict, Any
import uuid
from datetime import datetime, timedelta

from app.core.config import settings
from app.models.echo import PresignedUrlRequest, PresignedUrlResponse

logger = logging.getLogger(__name__)


class S3Service:
    """Service for managing S3 operations"""
    
    def __init__(self):
        """Initialize S3 client"""
        try:
            self.s3_client = boto3.client(
                's3',
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            )
            self.bucket_name = settings.S3_BUCKET_NAME
            logger.info(f"S3 service initialized for bucket: {self.bucket_name}")
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise
    
    def generate_presigned_upload_url(
        self,
        user_id: str,
        request: PresignedUrlRequest
    ) -> PresignedUrlResponse:
        """
        Generate a presigned URL for uploading audio files to S3
        
        Args:
            user_id: User identifier
            request: Presigned URL request data
            
        Returns:
            PresignedUrlResponse with upload URL and metadata
            
        Raises:
            ClientError: If S3 operation fails
        """
        try:
            # Generate unique echo ID
            echo_id = str(uuid.uuid4())
            
            # Generate S3 key
            s3_key = settings.get_s3_key(user_id, echo_id, request.file_extension)
            
            # Generate presigned URL
            presigned_url = self.s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': s3_key,
                    'ContentType': request.content_type,
                    'ContentLength': settings.MAX_AUDIO_FILE_SIZE,
                    'Metadata': {
                        'user-id': user_id,
                        'echo-id': echo_id,
                        'upload-timestamp': datetime.utcnow().isoformat()
                    }
                },
                ExpiresIn=settings.S3_PRESIGNED_URL_EXPIRATION
            )
            
            logger.info(f"Generated presigned URL for user {user_id}, echo {echo_id}")
            
            return PresignedUrlResponse(
                upload_url=presigned_url,
                echo_id=echo_id,
                s3_key=s3_key,
                expires_in=settings.S3_PRESIGNED_URL_EXPIRATION
            )
            
        except ClientError as e:
            logger.error(f"S3 ClientError generating presigned URL: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error generating presigned URL: {e}")
            raise
    
    def generate_presigned_download_url(
        self,
        s3_key: str,
        expires_in: int = 3600
    ) -> str:
        """
        Generate a presigned URL for downloading audio files from S3
        
        Args:
            s3_key: S3 object key
            expires_in: URL expiration time in seconds
            
        Returns:
            Presigned download URL
            
        Raises:
            ClientError: If S3 operation fails
        """
        try:
            presigned_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': s3_key
                },
                ExpiresIn=expires_in
            )
            
            logger.debug(f"Generated download URL for key: {s3_key}")
            return presigned_url
            
        except ClientError as e:
            logger.error(f"S3 ClientError generating download URL: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error generating download URL: {e}")
            raise
    
    def check_file_exists(self, s3_key: str) -> bool:
        """
        Check if a file exists in S3
        
        Args:
            s3_key: S3 object key
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                return False
            else:
                logger.error(f"Error checking file existence: {e}")
                raise
    
    def get_file_metadata(self, s3_key: str) -> Optional[Dict[str, Any]]:
        """
        Get file metadata from S3
        
        Args:
            s3_key: S3 object key
            
        Returns:
            File metadata or None if file doesn't exist
        """
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return {
                'size': response.get('ContentLength', 0),
                'last_modified': response.get('LastModified'),
                'content_type': response.get('ContentType'),
                'metadata': response.get('Metadata', {})
            }
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.warning(f"File not found: {s3_key}")
                return None
            else:
                logger.error(f"Error getting file metadata: {e}")
                raise
    
    def delete_file(self, s3_key: str) -> bool:
        """
        Delete a file from S3
        
        Args:
            s3_key: S3 object key
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"Deleted file: {s3_key}")
            return True
        except ClientError as e:
            logger.error(f"Error deleting file {s3_key}: {e}")
            return False
    
    def ensure_bucket_exists(self) -> bool:
        """
        Ensure the S3 bucket exists (for development/testing)
        
        Returns:
            True if bucket exists or was created successfully
        """
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Bucket {self.bucket_name} exists")
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                try:
                    # Create bucket
                    if settings.AWS_REGION == 'us-east-1':
                        self.s3_client.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.s3_client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': settings.AWS_REGION}
                        )
                    logger.info(f"Created bucket {self.bucket_name}")
                    return True
                except ClientError as create_error:
                    logger.error(f"Error creating bucket: {create_error}")
                    return False
            else:
                logger.error(f"Error checking bucket: {e}")
                return False


# Global S3 service instance
s3_service = S3Service()