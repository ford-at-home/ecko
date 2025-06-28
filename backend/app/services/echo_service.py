"""
Echo service layer for business logic and data operations
"""
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import uuid

from app.models.echo import (
    Echo,
    EchoCreate,
    EchoResponse,
    EchoListResponse,
    EmotionType,
    PresignedUrlRequest,
    PresignedUrlResponse
)
from app.services.dynamodb_service import dynamodb_service
from app.services.s3_service import s3_service
from app.core.config import settings

logger = logging.getLogger(__name__)


class EchoServiceError(Exception):
    """Base exception for echo service errors"""
    pass


class EchoNotFoundError(EchoServiceError):
    """Raised when an echo is not found"""
    pass


class EchoValidationError(EchoServiceError):
    """Raised when echo validation fails"""
    pass


class EchoService:
    """Service for managing echo operations"""
    
    def __init__(self):
        """Initialize echo service with dependencies"""
        self.dynamodb_service = dynamodb_service
        self.s3_service = s3_service
    
    async def init_upload(
        self,
        user_id: str,
        request: PresignedUrlRequest
    ) -> PresignedUrlResponse:
        """
        Initialize audio upload by generating presigned URL
        
        Args:
            user_id: User identifier
            request: Upload request with file details
            
        Returns:
            Presigned URL response with upload details
            
        Raises:
            EchoServiceError: If presigned URL generation fails
        """
        try:
            logger.info(f"Initializing upload for user {user_id}")
            
            # Validate file extension and content type
            if request.file_extension not in settings.ALLOWED_AUDIO_FORMATS:
                raise EchoValidationError(
                    f"File extension '{request.file_extension}' not allowed. "
                    f"Allowed formats: {', '.join(settings.ALLOWED_AUDIO_FORMATS)}"
                )
            
            # Generate presigned URL
            response = self.s3_service.generate_presigned_upload_url(
                user_id=user_id,
                request=request
            )
            
            logger.info(f"Generated presigned URL for echo {response.echo_id}")
            return response
            
        except Exception as e:
            logger.error(f"Error initializing upload: {e}")
            raise EchoServiceError(f"Failed to initialize upload: {str(e)}")
    
    async def create_echo(
        self,
        user_id: str,
        echo_id: str,
        echo_data: EchoCreate
    ) -> EchoResponse:
        """
        Create a new echo with metadata
        
        Args:
            user_id: User identifier
            echo_id: Echo identifier from init_upload
            echo_data: Echo creation data
            
        Returns:
            Created echo response
            
        Raises:
            EchoValidationError: If echo data is invalid
            EchoServiceError: If creation fails
        """
        try:
            logger.info(f"Creating echo {echo_id} for user {user_id}")
            
            # Validate echo_id format
            try:
                uuid.UUID(echo_id)
            except ValueError:
                raise EchoValidationError(f"Invalid echo_id format: {echo_id}")
            
            # Generate S3 key and URL
            s3_key = settings.get_s3_key(user_id, echo_id, echo_data.file_extension)
            s3_url = settings.get_s3_url(s3_key)
            
            # Verify file exists in S3 (with retry logic)
            file_exists = self.s3_service.check_file_exists(s3_key)
            if not file_exists:
                logger.warning(f"Audio file not found in S3: {s3_key}")
                # Still proceed as upload might be in progress
            
            # Get file metadata if available
            file_metadata = self.s3_service.get_file_metadata(s3_key)
            file_size = file_metadata.get('size') if file_metadata else None
            
            # Create Echo instance
            now = datetime.utcnow()
            echo = Echo(
                echo_id=echo_id,
                user_id=user_id,
                timestamp=now,
                s3_url=s3_url,
                s3_key=s3_key,
                emotion=echo_data.emotion,
                tags=echo_data.tags,
                transcript=echo_data.transcript,
                detected_mood=echo_data.detected_mood,
                location=echo_data.location,
                duration_seconds=echo_data.duration_seconds,
                file_size=file_size,
                created_at=now,
                updated_at=now
            )
            
            # Save to DynamoDB
            created_echo = self.dynamodb_service.create_echo(echo)
            
            logger.info(f"Successfully created echo {echo_id}")
            
            # Convert to response model
            return self._convert_to_response(created_echo)
            
        except EchoValidationError:
            raise
        except ValueError as e:
            logger.error(f"Validation error creating echo: {e}")
            raise EchoValidationError(str(e))
        except Exception as e:
            logger.error(f"Error creating echo: {e}")
            raise EchoServiceError(f"Failed to create echo: {str(e)}")
    
    async def get_echo(
        self,
        user_id: str,
        echo_id: str,
        include_download_url: bool = False
    ) -> EchoResponse:
        """
        Get a specific echo by ID
        
        Args:
            user_id: User identifier
            echo_id: Echo identifier
            include_download_url: Whether to include presigned download URL
            
        Returns:
            Echo response
            
        Raises:
            EchoNotFoundError: If echo not found
            EchoServiceError: If retrieval fails
        """
        try:
            logger.info(f"Getting echo {echo_id} for user {user_id}")
            
            echo = self.dynamodb_service.get_echo(user_id, echo_id)
            
            if not echo:
                raise EchoNotFoundError(f"Echo {echo_id} not found")
            
            response = self._convert_to_response(echo)
            
            # Generate download URL if requested
            if include_download_url:
                try:
                    download_url = self.s3_service.generate_presigned_download_url(
                        echo.s3_key,
                        expires_in=3600  # 1 hour
                    )
                    # Add download URL to response (extend model if needed)
                    response.s3_url = download_url
                except Exception as e:
                    logger.warning(f"Failed to generate download URL: {e}")
            
            return response
            
        except EchoNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error getting echo: {e}")
            raise EchoServiceError(f"Failed to get echo: {str(e)}")
    
    async def list_echoes(
        self,
        user_id: str,
        emotion: Optional[EmotionType] = None,
        tags: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
        last_evaluated_key: Optional[str] = None
    ) -> EchoListResponse:
        """
        List echoes for a user with advanced filtering and pagination
        
        Args:
            user_id: User identifier
            emotion: Optional emotion filter
            tags: Optional tags filter (any tag matches)
            start_date: Optional start date filter
            end_date: Optional end date filter
            page: Page number (1-based)
            page_size: Items per page (1-100)
            last_evaluated_key: DynamoDB pagination key
            
        Returns:
            Paginated list of echoes
            
        Raises:
            EchoValidationError: If parameters are invalid
            EchoServiceError: If listing fails
        """
        try:
            logger.info(f"Listing echoes for user {user_id}, emotion={emotion}")
            
            # Validate parameters
            if page < 1:
                raise EchoValidationError("Page must be >= 1")
            if page_size < 1 or page_size > 100:
                raise EchoValidationError("Page size must be between 1 and 100")
            
            # Get echoes from DynamoDB
            echoes, next_key = self.dynamodb_service.list_echoes(
                user_id=user_id,
                emotion=emotion,
                limit=page_size,
                last_evaluated_key=self._decode_pagination_key(last_evaluated_key)
            )
            
            # Apply additional filters
            filtered_echoes = self._apply_advanced_filters(
                echoes, tags, start_date, end_date
            )
            
            # Convert to response models
            echo_responses = [
                self._convert_to_response(echo)
                for echo in filtered_echoes
            ]
            
            # Calculate pagination info
            has_more = next_key is not None
            encoded_next_key = self._encode_pagination_key(next_key) if next_key else None
            
            response = EchoListResponse(
                echoes=echo_responses,
                total_count=len(echo_responses),  # Approximate for this page
                page=page,
                page_size=page_size,
                has_more=has_more
            )
            
            # Add pagination key to response (extend model if needed)
            if hasattr(response, 'next_key'):
                response.next_key = encoded_next_key
            
            logger.info(f"Returned {len(echo_responses)} echoes")
            return response
            
        except EchoValidationError:
            raise
        except Exception as e:
            logger.error(f"Error listing echoes: {e}")
            raise EchoServiceError(f"Failed to list echoes: {str(e)}")
    
    async def get_random_echo(
        self,
        user_id: str,
        emotion: Optional[EmotionType] = None
    ) -> EchoResponse:
        """
        Get a random echo for the user
        
        Args:
            user_id: User identifier
            emotion: Optional emotion filter
            
        Returns:
            Random echo response
            
        Raises:
            EchoNotFoundError: If no echoes found
            EchoServiceError: If retrieval fails
        """
        try:
            logger.info(f"Getting random echo for user {user_id}, emotion={emotion}")
            
            random_echo = self.dynamodb_service.get_random_echo(user_id, emotion)
            
            if not random_echo:
                raise EchoNotFoundError("No echoes found")
            
            logger.info(f"Selected random echo {random_echo.echo_id}")
            return self._convert_to_response(random_echo)
            
        except EchoNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error getting random echo: {e}")
            raise EchoServiceError(f"Failed to get random echo: {str(e)}")
    
    async def delete_echo(
        self,
        user_id: str,
        echo_id: str,
        delete_file: bool = True
    ) -> bool:
        """
        Delete an echo and optionally its associated file
        
        Args:
            user_id: User identifier
            echo_id: Echo identifier
            delete_file: Whether to delete S3 file
            
        Returns:
            True if deletion successful
            
        Raises:
            EchoNotFoundError: If echo not found
            EchoServiceError: If deletion fails
        """
        try:
            logger.info(f"Deleting echo {echo_id} for user {user_id}")
            
            # First get the echo to get S3 key
            echo = self.dynamodb_service.get_echo(user_id, echo_id)
            
            if not echo:
                raise EchoNotFoundError(f"Echo {echo_id} not found")
            
            # Delete from DynamoDB
            success = self.dynamodb_service.delete_echo(user_id, echo_id)
            
            if not success:
                raise EchoNotFoundError(f"Echo {echo_id} not found")
            
            # Delete from S3 if requested
            if delete_file:
                try:
                    self.s3_service.delete_file(echo.s3_key)
                    logger.info(f"Deleted S3 file: {echo.s3_key}")
                except Exception as e:
                    logger.warning(f"Failed to delete S3 file {echo.s3_key}: {e}")
                    # Don't fail the whole operation if S3 deletion fails
            
            logger.info(f"Successfully deleted echo {echo_id}")
            return True
            
        except EchoNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error deleting echo: {e}")
            raise EchoServiceError(f"Failed to delete echo: {str(e)}")
    
    async def get_user_statistics(self, user_id: str) -> Dict[str, Any]:
        """
        Get user's echo statistics with optimized queries
        
        Args:
            user_id: User identifier
            
        Returns:
            Statistics dictionary
        """
        try:
            logger.info(f"Getting statistics for user {user_id}")
            
            # Get total count efficiently
            total_count = self.dynamodb_service.get_echo_count(user_id)
            
            if total_count == 0:
                return {
                    'total_echoes': 0,
                    'emotion_distribution': {},
                    'total_duration_seconds': 0,
                    'average_duration_seconds': 0,
                    'oldest_echo_date': None,
                    'newest_echo_date': None,
                    'most_common_emotion': None
                }
            
            # Get emotion distribution by querying each emotion
            from app.models.echo import EmotionType
            emotion_counts = {}
            
            for emotion in EmotionType:
                count = self.dynamodb_service.get_echo_count(user_id, emotion)
                if count > 0:
                    emotion_counts[emotion.value] = count
            
            # Get sample of recent echoes for duration statistics
            recent_echoes, _ = self.dynamodb_service.list_echoes(
                user_id=user_id,
                limit=100  # Sample for duration calculation
            )
            
            # Calculate duration statistics from sample
            total_duration = 0
            duration_count = 0
            oldest_echo = None
            newest_echo = None
            
            for echo in recent_echoes:
                # Sum duration
                if echo.duration_seconds:
                    total_duration += echo.duration_seconds
                    duration_count += 1
                
                # Track oldest/newest from sample
                if not oldest_echo or echo.timestamp < oldest_echo.timestamp:
                    oldest_echo = echo
                if not newest_echo or echo.timestamp > newest_echo.timestamp:
                    newest_echo = echo
            
            # Estimate total duration based on sample
            if duration_count > 0 and len(recent_echoes) > 0:
                avg_duration_in_sample = total_duration / duration_count
                estimated_total_duration = avg_duration_in_sample * total_count
                estimated_avg_duration = avg_duration_in_sample
            else:
                estimated_total_duration = 0
                estimated_avg_duration = 0
            
            return {
                'total_echoes': total_count,
                'emotion_distribution': emotion_counts,
                'total_duration_seconds': estimated_total_duration,
                'average_duration_seconds': estimated_avg_duration,
                'oldest_echo_date': oldest_echo.timestamp.isoformat() if oldest_echo else None,
                'newest_echo_date': newest_echo.timestamp.isoformat() if newest_echo else None,
                'most_common_emotion': max(emotion_counts, key=emotion_counts.get) if emotion_counts else None,
                'sample_size': len(recent_echoes),
                'duration_sample_size': duration_count
            }
            
        except Exception as e:
            logger.error(f"Error getting user statistics: {e}")
            raise EchoServiceError(f"Failed to get statistics: {str(e)}")
    
    def _convert_to_response(self, echo: Echo) -> EchoResponse:
        """Convert Echo model to EchoResponse"""
        return EchoResponse(
            echo_id=echo.echo_id,
            emotion=echo.emotion,
            timestamp=echo.timestamp,
            s3_url=echo.s3_url,
            location=echo.location,
            tags=echo.tags,
            transcript=echo.transcript,
            detected_mood=echo.detected_mood,
            duration_seconds=echo.duration_seconds,
            created_at=echo.created_at
        )
    
    def _apply_advanced_filters(
        self,
        echoes: List[Echo],
        tags: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Echo]:
        """Apply advanced filters to echo list"""
        filtered_echoes = echoes
        
        # Filter by tags (any tag matches)
        if tags:
            tags_lower = [tag.lower() for tag in tags]
            filtered_echoes = [
                echo for echo in filtered_echoes
                if any(tag.lower() in tags_lower for tag in echo.tags)
            ]
        
        # Filter by date range
        if start_date:
            filtered_echoes = [
                echo for echo in filtered_echoes
                if echo.timestamp >= start_date
            ]
        
        if end_date:
            filtered_echoes = [
                echo for echo in filtered_echoes
                if echo.timestamp <= end_date
            ]
        
        return filtered_echoes
    
    def _encode_pagination_key(self, key: Optional[Dict]) -> Optional[str]:
        """Encode DynamoDB pagination key for API response"""
        if not key:
            return None
        # In production, you'd want to encrypt/encode this properly
        import json
        import base64
        return base64.b64encode(json.dumps(key).encode()).decode()
    
    def _decode_pagination_key(self, encoded_key: Optional[str]) -> Optional[Dict]:
        """Decode pagination key from API request"""
        if not encoded_key:
            return None
        try:
            import json
            import base64
            return json.loads(base64.b64decode(encoded_key.encode()).decode())
        except Exception:
            logger.warning(f"Invalid pagination key: {encoded_key}")
            return None


# Global echo service instance
echo_service = EchoService()