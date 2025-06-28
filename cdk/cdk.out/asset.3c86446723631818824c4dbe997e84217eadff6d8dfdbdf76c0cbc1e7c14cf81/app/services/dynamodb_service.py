"""
DynamoDB service for echo metadata storage and retrieval
"""
import boto3
import logging
from botocore.exceptions import ClientError, NoCredentialsError
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import random
from decimal import Decimal

from app.core.config import settings
from app.models.echo import Echo, EchoCreate, EmotionType

logger = logging.getLogger(__name__)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder for DynamoDB Decimal types"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


class DynamoDBService:
    """Service for managing DynamoDB operations"""
    
    def __init__(self):
        """Initialize DynamoDB client and table"""
        try:
            # Initialize DynamoDB resource
            if settings.DYNAMODB_ENDPOINT_URL:
                # For local development with DynamoDB Local
                self.dynamodb = boto3.resource(
                    'dynamodb',
                    region_name=settings.AWS_REGION,
                    endpoint_url=settings.DYNAMODB_ENDPOINT_URL,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID or 'dummy',
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or 'dummy'
                )
            else:
                # For AWS DynamoDB
                self.dynamodb = boto3.resource(
                    'dynamodb',
                    region_name=settings.AWS_REGION,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
                )
            
            self.table = self.dynamodb.Table(settings.DYNAMODB_TABLE_NAME)
            logger.info(f"DynamoDB service initialized for table: {settings.DYNAMODB_TABLE_NAME}")
            
        except NoCredentialsError:
            logger.error("AWS credentials not found for DynamoDB")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize DynamoDB service: {e}")
            raise
    
    def _convert_to_dynamo_item(self, echo: Echo) -> Dict[str, Any]:
        """Convert Echo model to DynamoDB item format"""
        item = {
            'userId': echo.user_id,
            'echoId': echo.echo_id,
            'timestamp': echo.timestamp.isoformat(),
            'emotion': echo.emotion.value,
            's3Url': echo.s3_url,
            's3Key': echo.s3_key,
            'tags': echo.tags,
            'createdAt': echo.created_at.isoformat(),
            'updatedAt': echo.updated_at.isoformat()
        }
        
        # Add optional fields
        if echo.location:
            item['location'] = {
                'lat': Decimal(str(echo.location.lat)),
                'lng': Decimal(str(echo.location.lng))
            }
            if echo.location.address:
                item['location']['address'] = echo.location.address
        
        if echo.transcript:
            item['transcript'] = echo.transcript
        
        if echo.detected_mood:
            item['detectedMood'] = echo.detected_mood
        
        if echo.duration_seconds:
            item['durationSeconds'] = Decimal(str(echo.duration_seconds))
        
        if echo.file_size:
            item['fileSize'] = echo.file_size
        
        return item
    
    def _convert_from_dynamo_item(self, item: Dict[str, Any]) -> Echo:
        """Convert DynamoDB item to Echo model"""
        # Handle location data
        location = None
        if 'location' in item:
            loc_data = item['location']
            location = {
                'lat': float(loc_data['lat']),
                'lng': float(loc_data['lng'])
            }
            if 'address' in loc_data:
                location['address'] = loc_data['address']
        
        echo_data = {
            'echo_id': item['echoId'],
            'user_id': item['userId'],
            'timestamp': datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00')),
            'emotion': EmotionType(item['emotion']),
            's3_url': item['s3Url'],
            's3_key': item['s3Key'],
            'tags': item.get('tags', []),
            'created_at': datetime.fromisoformat(item['createdAt'].replace('Z', '+00:00')),
            'updated_at': datetime.fromisoformat(item['updatedAt'].replace('Z', '+00:00')),
            'location': location,
            'transcript': item.get('transcript'),
            'detected_mood': item.get('detectedMood'),
            'duration_seconds': float(item['durationSeconds']) if 'durationSeconds' in item else None,
            'file_size': item.get('fileSize')
        }
        
        return Echo(**echo_data)
    
    def create_echo(self, echo: Echo) -> Echo:
        """
        Create a new echo in DynamoDB
        
        Args:
            echo: Echo instance to create
            
        Returns:
            Created Echo instance
            
        Raises:
            ClientError: If DynamoDB operation fails
        """
        try:
            item = self._convert_to_dynamo_item(echo)
            
            # Use conditional expression to prevent duplicates
            self.table.put_item(
                Item=item,
                ConditionExpression='attribute_not_exists(echoId)'
            )
            
            logger.info(f"Created echo {echo.echo_id} for user {echo.user_id}")
            return echo
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.error(f"Echo {echo.echo_id} already exists")
                raise ValueError(f"Echo {echo.echo_id} already exists")
            else:
                logger.error(f"DynamoDB error creating echo: {e}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error creating echo: {e}")
            raise
    
    def get_echo(self, user_id: str, echo_id: str) -> Optional[Echo]:
        """
        Get a specific echo by user ID and echo ID
        
        Args:
            user_id: User identifier
            echo_id: Echo identifier
            
        Returns:
            Echo instance or None if not found
        """
        try:
            response = self.table.get_item(
                Key={
                    'userId': user_id,
                    'echoId': echo_id
                }
            )
            
            if 'Item' in response:
                return self._convert_from_dynamo_item(response['Item'])
            
            return None
            
        except ClientError as e:
            logger.error(f"DynamoDB error getting echo: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting echo: {e}")
            raise
    
    def list_echoes(
        self,
        user_id: str,
        emotion: Optional[EmotionType] = None,
        limit: int = 20,
        last_evaluated_key: Optional[Dict] = None
    ) -> tuple[List[Echo], Optional[Dict]]:
        """
        List echoes for a user with optional emotion filtering
        
        Args:
            user_id: User identifier
            emotion: Optional emotion filter
            limit: Maximum number of echoes to return
            last_evaluated_key: Pagination key
            
        Returns:
            Tuple of (echoes list, next pagination key)
        """
        try:
            query_params = {
                'KeyConditionExpression': 'userId = :userId',
                'ExpressionAttributeValues': {':userId': user_id},
                'Limit': limit,
                'ScanIndexForward': False  # Sort by timestamp descending
            }
            
            if last_evaluated_key:
                query_params['ExclusiveStartKey'] = last_evaluated_key
            
            # Add emotion filter if specified
            if emotion:
                query_params['FilterExpression'] = 'emotion = :emotion'
                query_params['ExpressionAttributeValues'][':emotion'] = emotion.value
            
            response = self.table.query(**query_params)
            
            echoes = [
                self._convert_from_dynamo_item(item)
                for item in response.get('Items', [])
            ]
            
            next_key = response.get('LastEvaluatedKey')
            
            logger.debug(f"Retrieved {len(echoes)} echoes for user {user_id}")
            return echoes, next_key
            
        except ClientError as e:
            logger.error(f"DynamoDB error listing echoes: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error listing echoes: {e}")
            raise
    
    def get_random_echo(
        self,
        user_id: str,
        emotion: Optional[EmotionType] = None
    ) -> Optional[Echo]:
        """
        Get a random echo for a user with optional emotion filtering
        
        Args:
            user_id: User identifier
            emotion: Optional emotion filter
            
        Returns:
            Random Echo instance or None if no echoes found
        """
        try:
            # First, get all matching echoes
            all_echoes = []
            last_key = None
            
            while True:
                echoes, last_key = self.list_echoes(
                    user_id=user_id,
                    emotion=emotion,
                    limit=100,  # Process in chunks
                    last_evaluated_key=last_key
                )
                all_echoes.extend(echoes)
                
                if not last_key:
                    break
            
            if not all_echoes:
                return None
            
            # Return random echo
            random_echo = random.choice(all_echoes)
            logger.info(f"Selected random echo {random_echo.echo_id} for user {user_id}")
            return random_echo
            
        except Exception as e:
            logger.error(f"Error getting random echo: {e}")
            raise
    
    def update_echo(self, echo: Echo) -> Echo:
        """
        Update an existing echo
        
        Args:
            echo: Echo instance with updated data
            
        Returns:
            Updated Echo instance
        """
        try:
            echo.updated_at = datetime.utcnow()
            item = self._convert_to_dynamo_item(echo)
            
            self.table.put_item(
                Item=item,
                ConditionExpression='attribute_exists(echoId)'
            )
            
            logger.info(f"Updated echo {echo.echo_id} for user {echo.user_id}")
            return echo
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.error(f"Echo {echo.echo_id} does not exist")
                raise ValueError(f"Echo {echo.echo_id} does not exist")
            else:
                logger.error(f"DynamoDB error updating echo: {e}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error updating echo: {e}")
            raise
    
    def delete_echo(self, user_id: str, echo_id: str) -> bool:
        """
        Delete an echo
        
        Args:
            user_id: User identifier
            echo_id: Echo identifier
            
        Returns:
            True if deletion successful
        """
        try:
            self.table.delete_item(
                Key={
                    'userId': user_id,
                    'echoId': echo_id
                },
                ConditionExpression='attribute_exists(echoId)'
            )
            
            logger.info(f"Deleted echo {echo_id} for user {user_id}")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.warning(f"Echo {echo_id} does not exist for deletion")
                return False
            else:
                logger.error(f"DynamoDB error deleting echo: {e}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error deleting echo: {e}")
            raise
    
    def create_table_if_not_exists(self):
        """Create the DynamoDB table if it doesn't exist (for development)"""
        try:
            # Check if table exists
            self.table.load()
            logger.info(f"Table {settings.DYNAMODB_TABLE_NAME} already exists")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                # Create table
                table = self.dynamodb.create_table(
                    TableName=settings.DYNAMODB_TABLE_NAME,
                    KeySchema=[
                        {'AttributeName': 'userId', 'KeyType': 'HASH'},
                        {'AttributeName': 'echoId', 'KeyType': 'RANGE'}
                    ],
                    AttributeDefinitions=[
                        {'AttributeName': 'userId', 'AttributeType': 'S'},
                        {'AttributeName': 'echoId', 'AttributeType': 'S'},
                        {'AttributeName': 'emotion', 'AttributeType': 'S'},
                        {'AttributeName': 'timestamp', 'AttributeType': 'S'}
                    ],
                    GlobalSecondaryIndexes=[
                        {
                            'IndexName': 'emotion-timestamp-index',
                            'KeySchema': [
                                {'AttributeName': 'emotion', 'KeyType': 'HASH'},
                                {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                            ],
                            'Projection': {'ProjectionType': 'ALL'},
                            'BillingMode': 'PAY_PER_REQUEST'
                        }
                    ],
                    BillingMode='PAY_PER_REQUEST'
                )
                
                # Wait for table to be created
                table.wait_until_exists()
                logger.info(f"Created table {settings.DYNAMODB_TABLE_NAME}")
            else:
                logger.error(f"Error checking table existence: {e}")
                raise


# Global DynamoDB service instance
dynamodb_service = DynamoDBService()