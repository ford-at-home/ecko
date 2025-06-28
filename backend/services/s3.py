"""
Enhanced S3 service for audio file storage with secure presigned URLs
Includes comprehensive validation, user/timestamp structure, and cleanup utilities
"""
import boto3
import logging
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Optional, Dict, Any, List
import uuid
from datetime import datetime, timedelta
import mimetypes
import os

logger = logging.getLogger(__name__)


class S3AudioService:
    """Enhanced S3 service for audio file management with security focus"""
    
    # Supported audio formats and their MIME types
    AUDIO_FORMATS = {
        'webm': 'audio/webm',
        'wav': 'audio/wav',
        'mp3': 'audio/mpeg',
        'm4a': 'audio/mp4',
        'ogg': 'audio/ogg',
        'flac': 'audio/flac',
        'aac': 'audio/aac'
    }
    
    # Maximum file size (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    # Presigned URL expiration (1 hour)
    DEFAULT_EXPIRATION = 3600
    
    def __init__(self, bucket_name: str, region: str = 'us-east-1', aws_profile: str = None):
        """
        Initialize S3 service with personal AWS profile support
        
        Args:
            bucket_name: S3 bucket name for audio files
            region: AWS region
            aws_profile: AWS profile name for personal credentials
        """
        self.bucket_name = bucket_name
        self.region = region
        
        try:
            # Use personal AWS profile if specified
            if aws_profile:
                session = boto3.Session(profile_name=aws_profile)
                self.s3_client = session.client('s3', region_name=region)
                logger.info(f"S3 service initialized with profile: {aws_profile}")
            else:
                # Use environment credentials or instance role
                self.s3_client = boto3.client('s3', region_name=region)
                logger.info("S3 service initialized with default credentials")
                
            # Verify bucket access
            self._verify_bucket_access()
            
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise
    
    def _verify_bucket_access(self) -> bool:
        """Verify access to the S3 bucket"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Verified access to bucket: {self.bucket_name}")
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.error(f"Bucket not found: {self.bucket_name}")
            elif error_code == '403':
                logger.error(f"Access denied to bucket: {self.bucket_name}")
            else:
                logger.error(f"Error accessing bucket: {e}")
            raise
    
    def generate_s3_key(self, user_id: str, file_extension: str, echo_id: str = None) -> tuple:
        """
        Generate S3 key with user/timestamp structure
        
        Args:
            user_id: User identifier
            file_extension: File extension
            echo_id: Optional echo ID (generates new if not provided)
            
        Returns:
            Tuple of (s3_key, echo_id)
        """
        if not echo_id:
            echo_id = str(uuid.uuid4())
        
        # Create timestamp-based path structure
        now = datetime.utcnow()
        year = now.strftime('%Y')
        month = now.strftime('%m')
        day = now.strftime('%d')
        
        # Structure: user_id/year/month/day/echo_id.extension
        s3_key = f"{user_id}/{year}/{month}/{day}/{echo_id}.{file_extension}"
        
        return s3_key, echo_id
    
    def validate_audio_file(self, file_extension: str, content_type: str, file_size: int = None) -> bool:
        """
        Validate audio file parameters
        
        Args:
            file_extension: File extension
            content_type: MIME type
            file_size: File size in bytes (optional)
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If validation fails
        """
        # Validate extension
        ext = file_extension.lower().lstrip('.')
        if ext not in self.AUDIO_FORMATS:
            raise ValueError(f"Unsupported audio format: {ext}")
        
        # Validate content type
        expected_type = self.AUDIO_FORMATS[ext]
        if content_type != expected_type:
            raise ValueError(f"Content type {content_type} doesn't match extension {ext}")
        
        # Validate file size if provided
        if file_size and file_size > self.MAX_FILE_SIZE:
            raise ValueError(f"File size {file_size} exceeds maximum {self.MAX_FILE_SIZE}")
        
        return True
    
    def generate_presigned_upload_url(
        self,
        user_id: str,
        file_extension: str,
        content_type: str,
        file_size: int = None,
        echo_id: str = None,
        expires_in: int = DEFAULT_EXPIRATION
    ) -> Dict[str, Any]:
        """
        Generate secure presigned URL for audio upload
        
        Args:
            user_id: User identifier
            file_extension: File extension
            content_type: MIME type
            file_size: File size in bytes (optional)
            echo_id: Optional echo ID
            expires_in: URL expiration in seconds
            
        Returns:
            Dictionary with upload details
        """
        try:
            # Validate input
            self.validate_audio_file(file_extension, content_type, file_size)
            
            # Generate S3 key
            s3_key, final_echo_id = self.generate_s3_key(user_id, file_extension, echo_id)
            
            # Prepare conditions for presigned URL
            conditions = [
                {"bucket": self.bucket_name},
                {"key": s3_key},
                {"Content-Type": content_type},
                {"x-amz-server-side-encryption": "AES256"},
                ["content-length-range", 1, self.MAX_FILE_SIZE]
            ]
            
            # Additional metadata
            metadata = {
                'user-id': user_id,
                'echo-id': final_echo_id,
                'upload-timestamp': datetime.utcnow().isoformat(),
                'client-type': 'web'
            }
            
            # Generate presigned URL with security headers
            presigned_data = self.s3_client.generate_presigned_post(
                Bucket=self.bucket_name,
                Key=s3_key,
                Fields={
                    'Content-Type': content_type,
                    'x-amz-server-side-encryption': 'AES256',
                    'x-amz-meta-user-id': user_id,
                    'x-amz-meta-echo-id': final_echo_id,
                    'x-amz-meta-upload-timestamp': metadata['upload-timestamp']
                },
                Conditions=conditions,
                ExpiresIn=expires_in
            )
            
            logger.info(f"Generated secure presigned URL for user {user_id}, echo {final_echo_id}")
            
            return {
                'upload_url': presigned_data['url'],
                'upload_fields': presigned_data['fields'],
                'echo_id': final_echo_id,
                's3_key': s3_key,
                's3_url': f"s3://{self.bucket_name}/{s3_key}",
                'expires_in': expires_in,
                'max_file_size': self.MAX_FILE_SIZE,
                'metadata': metadata
            }
            
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            raise
        except ClientError as e:
            logger.error(f"S3 error generating presigned URL: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise
    
    def generate_presigned_download_url(
        self,
        s3_key: str,
        expires_in: int = 3600
    ) -> str:
        """
        Generate presigned URL for downloading audio files
        
        Args:
            s3_key: S3 object key
            expires_in: URL expiration in seconds
            
        Returns:
            Presigned download URL
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': s3_key
                },
                ExpiresIn=expires_in
            )
            
            logger.debug(f"Generated download URL for key: {s3_key}")
            return url
            
        except ClientError as e:
            logger.error(f"Error generating download URL: {e}")
            raise
    
    def check_file_exists(self, s3_key: str) -> bool:
        """Check if file exists in S3"""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise
    
    def get_file_metadata(self, s3_key: str) -> Optional[Dict[str, Any]]:
        """Get file metadata from S3"""
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return {
                'size': response.get('ContentLength', 0),
                'last_modified': response.get('LastModified'),
                'content_type': response.get('ContentType'),
                'etag': response.get('ETag', '').strip('"'),
                'metadata': response.get('Metadata', {}),
                'server_side_encryption': response.get('ServerSideEncryption')
            }
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return None
            raise
    
    def delete_file(self, s3_key: str) -> bool:
        """Delete file from S3"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"Deleted S3 file: {s3_key}")
            return True
        except ClientError as e:
            logger.error(f"Error deleting file {s3_key}: {e}")
            return False
    
    def cleanup_user_files(self, user_id: str, older_than_days: int = 365) -> int:
        """
        Cleanup old files for a user
        
        Args:
            user_id: User identifier
            older_than_days: Delete files older than this many days
            
        Returns:
            Number of files deleted
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
            deleted_count = 0
            
            # List objects with user prefix
            paginator = self.s3_client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=f"{user_id}/"):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        if obj['LastModified'].replace(tzinfo=None) < cutoff_date:
                            self.delete_file(obj['Key'])
                            deleted_count += 1
            
            logger.info(f"Cleaned up {deleted_count} old files for user {user_id}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error during cleanup for user {user_id}: {e}")
            return 0
    
    def get_user_storage_stats(self, user_id: str) -> Dict[str, Any]:
        """Get storage statistics for a user"""
        try:
            total_size = 0
            file_count = 0
            
            paginator = self.s3_client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=f"{user_id}/"):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        total_size += obj['Size']
                        file_count += 1
            
            return {
                'user_id': user_id,
                'total_files': file_count,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2)
            }
            
        except Exception as e:
            logger.error(f"Error getting storage stats for user {user_id}: {e}")
            return {'error': str(e)}


def create_s3_service(bucket_name: str, region: str = 'us-east-1', aws_profile: str = None) -> S3AudioService:
    """
    Factory function to create S3 service instance
    
    Args:
        bucket_name: S3 bucket name
        region: AWS region
        aws_profile: AWS profile name for personal credentials
        
    Returns:
        S3AudioService instance
    """
    return S3AudioService(bucket_name, region, aws_profile)


# Configuration helper functions
def get_bucket_cors_configuration() -> Dict[str, Any]:
    """Get recommended CORS configuration for audio bucket"""
    return {
        "CORSRules": [
            {
                "ID": "EchoesAudioUpload",
                "AllowedHeaders": ["*"],
                "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
                "AllowedOrigins": [
                    "http://localhost:3000",
                    "http://127.0.0.1:3000",
                    "https://*.echoes.app"
                ],
                "ExposeHeaders": ["ETag", "x-amz-meta-*"],
                "MaxAgeSeconds": 3000
            }
        ]
    }


def get_bucket_policy_template(bucket_name: str, region: str = 'us-east-1') -> Dict[str, Any]:
    """Get recommended bucket policy template"""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowAuthenticatedUploads",
                "Effect": "Allow",
                "Principal": "*",
                "Action": ["s3:PutObject", "s3:PutObjectAcl"],
                "Resource": f"arn:aws:s3:::{bucket_name}/*",
                "Condition": {
                    "StringEquals": {
                        "s3:x-amz-server-side-encryption": "AES256"
                    }
                }
            },
            {
                "Sid": "AllowUserFileAccess",
                "Effect": "Allow",
                "Principal": "*",
                "Action": ["s3:GetObject", "s3:DeleteObject"],
                "Resource": f"arn:aws:s3:::{bucket_name}/*"
            }
        ]
    }