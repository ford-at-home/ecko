"""
DynamoDB Service for Echoes App
Handles echo metadata storage and retrieval
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from boto3.dynamodb.conditions import Key, Attr
from pydantic import BaseModel


class EchoMetadata(BaseModel):
    """Echo metadata model"""
    user_id: str
    echo_id: str
    emotion: str
    timestamp: str
    s3_url: str
    s3_key: str
    location: Optional[Dict[str, float]] = None
    tags: List[str] = []
    transcript: Optional[str] = None
    detected_mood: Optional[str] = None
    audio_duration: float = 0.0
    audio_sample_rate: int = 0
    audio_channels: int = 0
    audio_format: str = ""
    created_at: str = ""
    updated_at: str = ""


class DynamoDBConfig:
    """DynamoDB configuration"""
    TABLE_NAME = os.getenv('DYNAMODB_TABLE_NAME', 'EchoesTable')
    REGION = os.getenv('AWS_REGION', 'us-east-1')
    GSI_EMOTION_NAME = 'emotion-timestamp-index'


class DynamoDBService:
    """
    AWS DynamoDB service for echo metadata management
    """
    
    def __init__(self, config: Optional[DynamoDBConfig] = None):
        self.config = config or DynamoDBConfig()
        self.logger = logging.getLogger(__name__)
        
        # Initialize DynamoDB resource
        try:
            # In Lambda, use IAM role credentials instead of explicit keys
            if os.getenv('AWS_LAMBDA_FUNCTION_NAME'):
                self.dynamodb = boto3.resource('dynamodb', region_name=self.config.REGION)
            else:
                self.dynamodb = boto3.resource(
                    'dynamodb',
                    region_name=self.config.REGION,
                    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
                )
            
            self.table = self.dynamodb.Table(self.config.TABLE_NAME)
            
            # Test connection (skip in Lambda to avoid permission issues during init)
            if not os.getenv('AWS_LAMBDA_FUNCTION_NAME'):
                self.table.load()
            self.logger.info(f"DynamoDB service initialized for table: {self.config.TABLE_NAME}")
            
        except NoCredentialsError:
            self.logger.error("AWS credentials not found")
            raise
        except ClientError as e:
            self.logger.error(f"Error connecting to DynamoDB: {e}")
            raise
    
    def create_echo(self, echo_data: Dict[str, Any]) -> EchoMetadata:
        """
        Create a new echo record
        
        Args:
            echo_data: Echo information dictionary
        
        Returns:
            Created echo metadata
        """
        try:
            # Generate echo ID if not provided
            echo_id = echo_data.get('echo_id', str(uuid.uuid4()))
            current_time = datetime.utcnow().isoformat()
            
            # Prepare item for DynamoDB
            item = {
                'userId': echo_data['user_id'],  # Partition key
                'echoId': echo_id,  # Sort key
                'emotion': echo_data['emotion'],
                'timestamp': echo_data.get('timestamp', current_time),
                's3Url': echo_data['s3_url'],
                's3Key': echo_data['s3_key'],
                'location': echo_data.get('location', {}),
                'tags': echo_data.get('tags', []),
                'transcript': echo_data.get('transcript', ''),
                'detectedMood': echo_data.get('detected_mood', ''),
                'audioDuration': echo_data.get('audio_duration', 0.0),
                'audioSampleRate': echo_data.get('audio_sample_rate', 0),
                'audioChannels': echo_data.get('audio_channels', 0),
                'audioFormat': echo_data.get('audio_format', ''),
                'createdAt': current_time,
                'updatedAt': current_time
            }
            
            # Insert item
            self.table.put_item(Item=item)
            
            self.logger.info(f"Created echo {echo_id} for user {echo_data['user_id']}")
            
            # Return as EchoMetadata model
            return EchoMetadata(
                user_id=item['userId'],
                echo_id=item['echoId'],
                emotion=item['emotion'],
                timestamp=item['timestamp'],
                s3_url=item['s3Url'],
                s3_key=item['s3Key'],
                location=item.get('location'),
                tags=item.get('tags', []),
                transcript=item.get('transcript'),
                detected_mood=item.get('detectedMood'),
                audio_duration=item.get('audioDuration', 0.0),
                audio_sample_rate=item.get('audioSampleRate', 0),
                audio_channels=item.get('audioChannels', 0),
                audio_format=item.get('audioFormat', ''),
                created_at=item['createdAt'],
                updated_at=item['updatedAt']
            )
            
        except Exception as e:
            self.logger.error(f"Error creating echo: {e}")
            raise
    
    def get_echo(self, user_id: str, echo_id: str) -> Optional[EchoMetadata]:
        """
        Get a specific echo by user ID and echo ID
        
        Args:
            user_id: User identifier
            echo_id: Echo identifier
        
        Returns:
            Echo metadata or None if not found
        """
        try:
            response = self.table.get_item(
                Key={
                    'userId': user_id,
                    'echoId': echo_id
                }
            )
            
            if 'Item' not in response:
                self.logger.warning(f"Echo not found: {user_id}/{echo_id}")
                return None
            
            item = response['Item']
            
            return EchoMetadata(
                user_id=item['userId'],
                echo_id=item['echoId'],
                emotion=item['emotion'],
                timestamp=item['timestamp'],
                s3_url=item['s3Url'],
                s3_key=item['s3Key'],
                location=item.get('location'),
                tags=item.get('tags', []),
                transcript=item.get('transcript'),
                detected_mood=item.get('detectedMood'),
                audio_duration=item.get('audioDuration', 0.0),
                audio_sample_rate=item.get('audioSampleRate', 0),
                audio_channels=item.get('audioChannels', 0),
                audio_format=item.get('audioFormat', ''),
                created_at=item.get('createdAt', ''),
                updated_at=item.get('updatedAt', '')
            )
            
        except Exception as e:
            self.logger.error(f"Error getting echo: {e}")
            raise
    
    def list_user_echoes(self, user_id: str, limit: int = 50, last_key: Optional[Dict] = None) -> Dict[str, Any]:
        """
        List echoes for a user
        
        Args:
            user_id: User identifier
            limit: Maximum number of echoes to return
            last_key: Last evaluated key for pagination
        
        Returns:
            Dictionary with echoes list and pagination info
        """
        try:
            query_params = {
                'KeyConditionExpression': Key('userId').eq(user_id),
                'ScanIndexForward': False,  # Sort by timestamp descending
                'Limit': limit
            }
            
            if last_key:
                query_params['ExclusiveStartKey'] = last_key
            
            response = self.table.query(**query_params)
            
            echoes = []
            for item in response.get('Items', []):
                echoes.append(EchoMetadata(
                    user_id=item['userId'],
                    echo_id=item['echoId'],
                    emotion=item['emotion'],
                    timestamp=item['timestamp'],
                    s3_url=item['s3Url'],
                    s3_key=item['s3Key'],
                    location=item.get('location'),
                    tags=item.get('tags', []),
                    transcript=item.get('transcript'),
                    detected_mood=item.get('detectedMood'),
                    audio_duration=item.get('audioDuration', 0.0),
                    audio_sample_rate=item.get('audioSampleRate', 0),
                    audio_channels=item.get('audioChannels', 0),
                    audio_format=item.get('audioFormat', ''),
                    created_at=item.get('createdAt', ''),
                    updated_at=item.get('updatedAt', '')
                ))
            
            result = {
                'echoes': [echo.dict() for echo in echoes],
                'count': len(echoes),
                'last_evaluated_key': response.get('LastEvaluatedKey')
            }
            
            self.logger.info(f"Retrieved {len(echoes)} echoes for user {user_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error listing user echoes: {e}")
            raise
    
    def filter_echoes_by_emotion(self, user_id: str, emotion: str, limit: int = 50) -> List[EchoMetadata]:
        """
        Filter echoes by emotion using GSI
        
        Args:
            user_id: User identifier
            emotion: Emotion to filter by
            limit: Maximum number of echoes to return
        
        Returns:
            List of matching echoes
        """
        try:
            # Query with emotion filter
            response = self.table.query(
                KeyConditionExpression=Key('userId').eq(user_id),
                FilterExpression=Attr('emotion').eq(emotion),
                ScanIndexForward=False,
                Limit=limit
            )
            
            echoes = []
            for item in response.get('Items', []):
                echoes.append(EchoMetadata(
                    user_id=item['userId'],
                    echo_id=item['echoId'],
                    emotion=item['emotion'],
                    timestamp=item['timestamp'],
                    s3_url=item['s3Url'],
                    s3_key=item['s3Key'],
                    location=item.get('location'),
                    tags=item.get('tags', []),
                    transcript=item.get('transcript'),
                    detected_mood=item.get('detectedMood'),
                    audio_duration=item.get('audioDuration', 0.0),
                    audio_sample_rate=item.get('audioSampleRate', 0),
                    audio_channels=item.get('audioChannels', 0),
                    audio_format=item.get('audioFormat', ''),
                    created_at=item.get('createdAt', ''),
                    updated_at=item.get('updatedAt', '')
                ))
            
            self.logger.info(f"Found {len(echoes)} echoes with emotion '{emotion}' for user {user_id}")
            return echoes
            
        except Exception as e:
            self.logger.error(f"Error filtering echoes by emotion: {e}")
            raise
    
    def get_random_echo_by_emotion(self, user_id: str, emotion: str) -> Optional[EchoMetadata]:
        """
        Get a random echo matching the specified emotion
        
        Args:
            user_id: User identifier
            emotion: Emotion to match
        
        Returns:
            Random matching echo or None
        """
        try:
            import random
            
            # Get all echoes with the emotion
            echoes = self.filter_echoes_by_emotion(user_id, emotion, limit=100)
            
            if not echoes:
                return None
            
            # Return random echo
            return random.choice(echoes)
            
        except Exception as e:
            self.logger.error(f"Error getting random echo: {e}")
            return None
    
    def update_echo(self, user_id: str, echo_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update echo metadata
        
        Args:
            user_id: User identifier
            echo_id: Echo identifier
            updates: Dictionary of fields to update
        
        Returns:
            Success status
        """
        try:
            # Prepare update expression
            update_expression = "SET updatedAt = :updated_at"
            expression_values = {':updated_at': datetime.utcnow().isoformat()}
            
            for field, value in updates.items():
                if field not in ['userId', 'echoId']:  # Don't update keys
                    update_expression += f", {field} = :{field}"
                    expression_values[f':{field}'] = value
            
            # Update item
            self.table.update_item(
                Key={
                    'userId': user_id,
                    'echoId': echo_id
                },
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values
            )
            
            self.logger.info(f"Updated echo {echo_id} for user {user_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating echo: {e}")
            return False
    
    def delete_echo(self, user_id: str, echo_id: str) -> bool:
        """
        Delete an echo record
        
        Args:
            user_id: User identifier
            echo_id: Echo identifier
        
        Returns:
            Success status
        """
        try:
            self.table.delete_item(
                Key={
                    'userId': user_id,
                    'echoId': echo_id
                }
            )
            
            self.logger.info(f"Deleted echo {echo_id} for user {user_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting echo: {e}")
            return False
    
    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get user statistics
        
        Args:
            user_id: User identifier
        
        Returns:
            User statistics dictionary
        """
        try:
            # Get all user echoes for stats
            response = self.table.query(
                KeyConditionExpression=Key('userId').eq(user_id),
                ProjectionExpression='emotion, audioDuration, createdAt'
            )
            
            items = response.get('Items', [])
            
            # Calculate statistics
            total_echoes = len(items)
            emotions = {}
            total_duration = 0.0
            
            for item in items:
                emotion = item.get('emotion', 'unknown')
                emotions[emotion] = emotions.get(emotion, 0) + 1
                total_duration += item.get('audioDuration', 0.0)
            
            stats = {
                'total_echoes': total_echoes,
                'total_duration_seconds': total_duration,
                'emotions_breakdown': emotions,
                'most_common_emotion': max(emotions.items(), key=lambda x: x[1])[0] if emotions else None
            }
            
            self.logger.info(f"Retrieved stats for user {user_id}: {total_echoes} echoes")
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting user stats: {e}")
            return {}
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on DynamoDB service
        
        Returns:
            Health status information
        """
        try:
            # Try to describe table
            self.table.load()
            
            return {
                "status": "healthy",
                "table_name": self.config.TABLE_NAME,
                "region": self.config.REGION,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"DynamoDB health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }


# Global DynamoDB service instance
dynamodb_service = DynamoDBService()