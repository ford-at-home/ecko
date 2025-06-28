"""
Integration tests for AWS services
Tests S3, DynamoDB, and authentication service integration
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import boto3
from moto import mock_s3, mock_dynamodb, mock_cognitoidp
import json

from backend.src.services.s3_service import S3Service, S3Config, UploadRequest
from backend.src.services.dynamodb_service import DynamoDBService, DynamoDBConfig
from backend.src.services.auth_service import AuthService, AuthConfig


@mock_s3
class TestS3ServiceIntegration:
    """Integration tests for S3 service with mocked AWS"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Create mock S3 bucket
        self.bucket_name = 'test-echoes-audio'
        self.region = 'us-east-1'
        
        # Create S3 client and bucket
        s3_client = boto3.client('s3', region_name=self.region)
        s3_client.create_bucket(Bucket=self.bucket_name)
        
        # Configure S3 service
        self.config = S3Config(
            bucket_name=self.bucket_name,
            region=self.region
        )
        
        with patch.dict(os.environ, {
            'S3_BUCKET_NAME': self.bucket_name,
            'AWS_ACCESS_KEY_ID': 'test',
            'AWS_SECRET_ACCESS_KEY': 'test'
        }):
            self.s3_service = S3Service(self.config)
    
    def test_generate_s3_key(self):
        """Test S3 key generation"""
        user_id = 'test-user-123'
        emotion = 'Joy'
        
        key = self.s3_service.generate_s3_key(user_id, emotion)
        
        assert key.startswith(f"{user_id}/{emotion}/")
        assert key.endswith('.webm')
        assert len(key.split('/')) == 3  # user_id/emotion/filename
    
    def test_validate_upload_request_success(self):
        """Test successful upload request validation"""
        request = UploadRequest(
            user_id='test-user',
            content_type='audio/webm',
            file_size=1024000,
            emotion='Calm',
            tags=['nature']
        )
        
        is_valid, error = self.s3_service.validate_upload_request(request)
        
        assert is_valid is True
        assert error == ""
    
    def test_validate_upload_request_invalid_content_type(self):
        """Test upload validation with invalid content type"""
        request = UploadRequest(
            user_id='test-user',
            content_type='video/mp4',  # Invalid
            file_size=1024000,
            emotion='Joy'
        )
        
        is_valid, error = self.s3_service.validate_upload_request(request)
        
        assert is_valid is False
        assert 'not allowed' in error
    
    def test_validate_upload_request_file_too_large(self):
        """Test upload validation with oversized file"""
        request = UploadRequest(
            user_id='test-user',
            content_type='audio/wav',
            file_size=100 * 1024 * 1024,  # 100MB - too large
            emotion='Joy'
        )
        
        is_valid, error = self.s3_service.validate_upload_request(request)
        
        assert is_valid is False
        assert 'exceeds limit' in error
    
    def test_generate_presigned_post(self):
        """Test presigned POST URL generation"""
        request = UploadRequest(
            user_id='test-user',
            content_type='audio/webm',
            file_size=1024000,
            emotion='Joy',
            tags=['test']
        )
        
        response = self.s3_service.generate_presigned_post(request)
        
        assert response.upload_url
        assert response.fields
        assert response.key
        assert response.expires_at > datetime.utcnow()
        assert response.max_file_size == self.config.max_file_size
        assert 'test-user/Joy/' in response.key
    
    def test_generate_presigned_get_url(self):
        """Test presigned GET URL generation"""
        s3_key = 'test-user/Joy/echo-123.webm'
        user_id = 'test-user'
        
        url = self.s3_service.generate_presigned_get_url(s3_key, user_id)
        
        assert url
        assert self.bucket_name in url
        assert s3_key in url
    
    def test_generate_presigned_get_url_unauthorized(self):
        """Test presigned GET URL with unauthorized access"""
        s3_key = 'other-user/Joy/echo-123.webm'
        user_id = 'test-user'  # Different user
        
        with pytest.raises(ValueError, match='Unauthorized'):
            self.s3_service.generate_presigned_get_url(s3_key, user_id)
    
    def test_delete_audio_file_success(self):
        """Test successful audio file deletion"""
        # First upload a file
        s3_key = 'test-user/Joy/echo-to-delete.webm'
        user_id = 'test-user'
        
        # Put object in S3
        self.s3_service.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=s3_key,
            Body=b'test audio data'
        )
        
        # Delete the file
        success = self.s3_service.delete_audio_file(s3_key, user_id)
        
        assert success is True
        
        # Verify file is deleted
        with pytest.raises(Exception):
            self.s3_service.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
    
    def test_delete_audio_file_unauthorized(self):
        """Test file deletion with unauthorized access"""
        s3_key = 'other-user/Joy/echo-123.webm'
        user_id = 'test-user'
        
        with pytest.raises(ValueError, match='Unauthorized'):
            self.s3_service.delete_audio_file(s3_key, user_id)
    
    def test_get_file_metadata(self):
        """Test file metadata retrieval"""
        s3_key = 'test-user/Joy/echo-metadata.webm'
        user_id = 'test-user'
        
        # Put object with metadata
        self.s3_service.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=s3_key,
            Body=b'test audio data',
            ContentType='audio/webm',
            Metadata={
                'user-id': user_id,
                'emotion': 'Joy'
            }
        )
        
        metadata = self.s3_service.get_file_metadata(s3_key, user_id)
        
        assert metadata is not None
        assert metadata['content_type'] == 'audio/webm'
        assert metadata['size'] > 0
        assert 'last_modified' in metadata
        assert 'user_metadata' in metadata
    
    def test_list_user_files(self):
        """Test listing user files"""
        user_id = 'test-user'
        
        # Put multiple files
        files = [
            'test-user/Joy/echo-1.webm',
            'test-user/Joy/echo-2.webm',
            'test-user/Calm/echo-3.webm'
        ]
        
        for s3_key in files:
            self.s3_service.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=b'test audio data'
            )
        
        # List all user files
        file_list = self.s3_service.list_user_files(user_id)
        
        assert len(file_list) == 3
        for file_info in file_list:
            assert file_info['key'].startswith(f"{user_id}/")
            assert 'size' in file_info
            assert 'last_modified' in file_info
    
    def test_health_check_success(self):
        """Test S3 service health check"""
        health = self.s3_service.health_check()
        
        assert health['status'] == 'healthy'
        assert health['bucket'] == self.bucket_name
        assert health['region'] == self.region


@mock_dynamodb
class TestDynamoDBServiceIntegration:
    """Integration tests for DynamoDB service with mocked AWS"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.table_name = 'TestEchoesTable'
        self.region = 'us-east-1'
        
        # Create DynamoDB table
        dynamodb = boto3.resource('dynamodb', region_name=self.region)
        
        table = dynamodb.create_table(
            TableName=self.table_name,
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
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                }
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        
        # Configure DynamoDB service
        self.config = DynamoDBConfig()
        self.config.TABLE_NAME = self.table_name
        
        with patch.dict(os.environ, {
            'DYNAMODB_TABLE_NAME': self.table_name,
            'AWS_ACCESS_KEY_ID': 'test',
            'AWS_SECRET_ACCESS_KEY': 'test'
        }):
            self.db_service = DynamoDBService(self.config)
    
    def test_create_echo(self):
        """Test echo creation"""
        echo_data = {
            'user_id': 'test-user',
            'emotion': 'Joy',
            's3_url': 's3://bucket/test-user/Joy/echo-1.webm',
            's3_key': 'test-user/Joy/echo-1.webm',
            'tags': ['nature', 'peaceful'],
            'location': {'lat': 37.7749, 'lng': -122.4194},
            'audio_duration': 15.5
        }
        
        echo = self.db_service.create_echo(echo_data)
        
        assert echo.user_id == 'test-user'
        assert echo.emotion == 'Joy'
        assert echo.s3_url == echo_data['s3_url']
        assert echo.tags == ['nature', 'peaceful']
        assert echo.audio_duration == 15.5
        assert echo.echo_id  # Should be generated
        assert echo.created_at  # Should be set
    
    def test_get_echo(self):
        """Test echo retrieval"""
        # First create an echo
        echo_data = {
            'user_id': 'test-user',
            'echo_id': 'test-echo-123',
            'emotion': 'Calm',
            's3_url': 's3://bucket/test-user/Calm/test-echo-123.webm',
            's3_key': 'test-user/Calm/test-echo-123.webm'
        }
        
        created_echo = self.db_service.create_echo(echo_data)
        
        # Retrieve the echo
        retrieved_echo = self.db_service.get_echo('test-user', created_echo.echo_id)
        
        assert retrieved_echo is not None
        assert retrieved_echo.user_id == 'test-user'
        assert retrieved_echo.emotion == 'Calm'
        assert retrieved_echo.echo_id == created_echo.echo_id
    
    def test_get_echo_not_found(self):
        """Test echo retrieval when not found"""
        echo = self.db_service.get_echo('test-user', 'nonexistent-echo')
        
        assert echo is None
    
    def test_list_user_echoes(self):
        """Test listing user echoes"""
        user_id = 'test-user'
        
        # Create multiple echoes
        echoes_data = [
            {
                'user_id': user_id,
                'emotion': 'Joy',
                's3_url': f's3://bucket/{user_id}/Joy/echo-1.webm',
                's3_key': f'{user_id}/Joy/echo-1.webm'
            },
            {
                'user_id': user_id,
                'emotion': 'Calm',
                's3_url': f's3://bucket/{user_id}/Calm/echo-2.webm',
                's3_key': f'{user_id}/Calm/echo-2.webm'
            }
        ]
        
        created_echoes = []
        for data in echoes_data:
            echo = self.db_service.create_echo(data)
            created_echoes.append(echo)
        
        # List echoes
        result = self.db_service.list_user_echoes(user_id)
        
        assert result['count'] == 2
        assert len(result['echoes']) == 2
        
        # Verify echoes are returned
        echo_ids = [echo['echo_id'] for echo in result['echoes']]
        assert created_echoes[0].echo_id in echo_ids
        assert created_echoes[1].echo_id in echo_ids
    
    def test_filter_echoes_by_emotion(self):
        """Test filtering echoes by emotion"""
        user_id = 'test-user'
        
        # Create echoes with different emotions
        echoes_data = [
            {
                'user_id': user_id,
                'emotion': 'Joy',
                's3_url': f's3://bucket/{user_id}/Joy/echo-1.webm',
                's3_key': f'{user_id}/Joy/echo-1.webm'
            },
            {
                'user_id': user_id,
                'emotion': 'Joy',
                's3_url': f's3://bucket/{user_id}/Joy/echo-2.webm',
                's3_key': f'{user_id}/Joy/echo-2.webm'
            },
            {
                'user_id': user_id,
                'emotion': 'Calm',
                's3_url': f's3://bucket/{user_id}/Calm/echo-3.webm',
                's3_key': f'{user_id}/Calm/echo-3.webm'
            }
        ]
        
        for data in echoes_data:
            self.db_service.create_echo(data)
        
        # Filter by Joy emotion
        joy_echoes = self.db_service.filter_echoes_by_emotion(user_id, 'Joy')
        
        assert len(joy_echoes) == 2
        for echo in joy_echoes:
            assert echo.emotion == 'Joy'
    
    def test_get_random_echo_by_emotion(self):
        """Test getting random echo by emotion"""
        user_id = 'test-user'
        
        # Create echoes with specific emotion
        for i in range(3):
            echo_data = {
                'user_id': user_id,
                'emotion': 'Peaceful',
                's3_url': f's3://bucket/{user_id}/Peaceful/echo-{i}.webm',
                's3_key': f'{user_id}/Peaceful/echo-{i}.webm'
            }
            self.db_service.create_echo(echo_data)
        
        # Get random echo
        random_echo = self.db_service.get_random_echo_by_emotion(user_id, 'Peaceful')
        
        assert random_echo is not None
        assert random_echo.emotion == 'Peaceful'
        assert random_echo.user_id == user_id
    
    def test_get_random_echo_not_found(self):
        """Test getting random echo when none exist"""
        random_echo = self.db_service.get_random_echo_by_emotion('test-user', 'Nonexistent')
        
        assert random_echo is None
    
    def test_update_echo(self):
        """Test echo update"""
        # Create echo
        echo_data = {
            'user_id': 'test-user',
            'emotion': 'Joy',
            's3_url': 's3://bucket/test-user/Joy/echo-update.webm',
            's3_key': 'test-user/Joy/echo-update.webm',
            'transcript': 'Original transcript'
        }
        
        echo = self.db_service.create_echo(echo_data)
        
        # Update echo
        updates = {
            'transcript': 'Updated transcript',
            'detectedMood': 'Happy'
        }
        
        success = self.db_service.update_echo('test-user', echo.echo_id, updates)
        
        assert success is True
        
        # Verify update
        updated_echo = self.db_service.get_echo('test-user', echo.echo_id)
        assert updated_echo.transcript == 'Updated transcript'
        assert updated_echo.detected_mood == 'Happy'
    
    def test_delete_echo(self):
        """Test echo deletion"""
        # Create echo
        echo_data = {
            'user_id': 'test-user',
            'emotion': 'Joy',
            's3_url': 's3://bucket/test-user/Joy/echo-delete.webm',
            's3_key': 'test-user/Joy/echo-delete.webm'
        }
        
        echo = self.db_service.create_echo(echo_data)
        
        # Delete echo
        success = self.db_service.delete_echo('test-user', echo.echo_id)
        
        assert success is True
        
        # Verify deletion
        deleted_echo = self.db_service.get_echo('test-user', echo.echo_id)
        assert deleted_echo is None
    
    def test_get_user_stats(self):
        """Test user statistics"""
        user_id = 'test-user'
        
        # Create echoes with different emotions and durations
        echoes_data = [
            {
                'user_id': user_id,
                'emotion': 'Joy',
                's3_url': f's3://bucket/{user_id}/Joy/echo-1.webm',
                's3_key': f'{user_id}/Joy/echo-1.webm',
                'audio_duration': 15.0
            },
            {
                'user_id': user_id,
                'emotion': 'Joy',
                's3_url': f's3://bucket/{user_id}/Joy/echo-2.webm',
                's3_key': f'{user_id}/Joy/echo-2.webm',
                'audio_duration': 20.0
            },
            {
                'user_id': user_id,
                'emotion': 'Calm',
                's3_url': f's3://bucket/{user_id}/Calm/echo-3.webm',
                's3_key': f'{user_id}/Calm/echo-3.webm',
                'audio_duration': 25.0
            }
        ]
        
        for data in echoes_data:
            self.db_service.create_echo(data)
        
        # Get stats
        stats = self.db_service.get_user_stats(user_id)
        
        assert stats['total_echoes'] == 3
        assert stats['total_duration_seconds'] == 60.0  # 15 + 20 + 25
        assert stats['emotions_breakdown']['Joy'] == 2
        assert stats['emotions_breakdown']['Calm'] == 1
        assert stats['most_common_emotion'] == 'Joy'
    
    def test_health_check(self):
        """Test DynamoDB service health check"""
        health = self.db_service.health_check()
        
        assert health['status'] == 'healthy'
        assert health['table_name'] == self.table_name
        assert health['region'] == self.region


@mock_cognitoidp
class TestAuthServiceIntegration:
    """Integration tests for authentication service with mocked Cognito"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.region = 'us-east-1'
        self.user_pool_id = 'us-east-1_TestPool'
        self.client_id = 'test-client-id'
        
        # Create Cognito client and user pool
        cognito_client = boto3.client('cognito-idp', region_name=self.region)
        
        # Create user pool
        user_pool = cognito_client.create_user_pool(
            PoolName='TestEchoesPool'
        )
        self.user_pool_id = user_pool['UserPool']['Id']
        
        # Create user pool client
        client_response = cognito_client.create_user_pool_client(
            UserPoolId=self.user_pool_id,
            ClientName='TestEchoesClient'
        )
        self.client_id = client_response['UserPoolClient']['ClientId']
        
        # Configure auth service
        self.config = AuthConfig()
        self.config.USER_POOL_ID = self.user_pool_id
        self.config.CLIENT_ID = self.client_id
        self.config.REGION = self.region
        
        with patch.dict(os.environ, {
            'COGNITO_USER_POOL_ID': self.user_pool_id,
            'COGNITO_CLIENT_ID': self.client_id,
            'AWS_REGION': self.region,
            'AWS_ACCESS_KEY_ID': 'test',
            'AWS_SECRET_ACCESS_KEY': 'test'
        }):
            self.auth_service = AuthService(self.config)
    
    def test_auth_service_initialization(self):
        """Test auth service initialization"""
        assert self.auth_service.config.USER_POOL_ID == self.user_pool_id
        assert self.auth_service.config.CLIENT_ID == self.client_id
        assert self.auth_service.config.REGION == self.region
    
    @patch('requests.get')
    def test_get_jwks_success(self, mock_get):
        """Test JWKS retrieval"""
        # Mock JWKS response
        mock_jwks = {
            'keys': [
                {
                    'kid': 'test-key-id',
                    'n': 'test-n-value',
                    'e': 'AQAB'
                }
            ]
        }
        
        mock_response = Mock()
        mock_response.json.return_value = mock_jwks
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        jwks = self.auth_service.get_jwks()
        
        assert 'keys' in jwks
        assert len(jwks['keys']) == 1
        assert jwks['keys'][0]['kid'] == 'test-key-id'
    
    @patch('requests.get')
    def test_get_jwks_caching(self, mock_get):
        """Test JWKS caching"""
        mock_jwks = {'keys': []}
        mock_response = Mock()
        mock_response.json.return_value = mock_jwks
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # First call
        jwks1 = self.auth_service.get_jwks()
        
        # Second call (should use cache)
        jwks2 = self.auth_service.get_jwks()
        
        # Should only make one HTTP request
        assert mock_get.call_count == 1
        assert jwks1 == jwks2
    
    def test_get_user_by_id(self):
        """Test getting user by ID"""
        # Create a user first
        user_attrs = [
            {'Name': 'email', 'Value': 'test@example.com'},
            {'Name': 'given_name', 'Value': 'Test'},
            {'Name': 'family_name', 'Value': 'User'}
        ]
        
        cognito_client = boto3.client('cognito-idp', region_name=self.region)
        
        user_response = cognito_client.admin_create_user(
            UserPoolId=self.user_pool_id,
            Username='testuser',
            UserAttributes=user_attrs,
            MessageAction='SUPPRESS'
        )
        
        user_id = user_response['User']['Username']
        
        # Get user details
        user_details = self.auth_service.get_user_by_id(user_id)
        
        assert user_details is not None
        assert user_details['username'] == 'testuser'
        assert user_details['attributes']['email'] == 'test@example.com'
    
    def test_get_user_by_id_not_found(self):
        """Test getting non-existent user"""
        user_details = self.auth_service.get_user_by_id('nonexistent-user')
        
        assert user_details is None
    
    def test_health_check(self):
        """Test auth service health check"""
        with patch.object(self.auth_service, 'get_jwks') as mock_jwks:
            mock_jwks.return_value = {'keys': [{'kid': 'test'}]}
            
            health = self.auth_service.health_check()
            
            assert health['status'] == 'healthy'
            assert health['user_pool_id'] == self.user_pool_id
            assert health['region'] == self.region
            assert health['jwks_keys_count'] == 1


class TestServiceIntegration:
    """Integration tests for multiple services working together"""
    
    @mock_s3
    @mock_dynamodb
    def test_complete_echo_workflow(self):
        """Test complete echo creation and retrieval workflow"""
        # Set up services
        bucket_name = 'test-echoes-audio'
        table_name = 'TestEchoesTable'
        region = 'us-east-1'
        
        # Create S3 bucket
        s3_client = boto3.client('s3', region_name=region)
        s3_client.create_bucket(Bucket=bucket_name)
        
        # Create DynamoDB table
        dynamodb = boto3.resource('dynamodb', region_name=region)
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {'AttributeName': 'userId', 'KeyType': 'HASH'},
                {'AttributeName': 'echoId', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'userId', 'AttributeType': 'S'},
                {'AttributeName': 'echoId', 'AttributeType': 'S'}
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        
        # Configure services
        with patch.dict(os.environ, {
            'S3_BUCKET_NAME': bucket_name,
            'DYNAMODB_TABLE_NAME': table_name,
            'AWS_ACCESS_KEY_ID': 'test',
            'AWS_SECRET_ACCESS_KEY': 'test'
        }):
            s3_config = S3Config(bucket_name=bucket_name, region=region)
            s3_service = S3Service(s3_config)
            
            db_config = DynamoDBConfig()
            db_config.TABLE_NAME = table_name
            db_service = DynamoDBService(db_config)
        
        # Step 1: Generate presigned URL
        upload_request = UploadRequest(
            user_id='test-user',
            content_type='audio/webm',
            file_size=1024000,
            emotion='Joy',
            tags=['integration', 'test']
        )
        
        presigned_response = s3_service.generate_presigned_post(upload_request)
        
        assert presigned_response.upload_url
        assert presigned_response.key
        
        # Step 2: Simulate file upload to S3
        s3_key = presigned_response.key
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=b'test audio data',
            ContentType='audio/webm'
        )
        
        # Step 3: Create echo metadata
        echo_data = {
            'user_id': 'test-user',
            'emotion': 'Joy',
            's3_url': f's3://{bucket_name}/{s3_key}',
            's3_key': s3_key,
            'tags': ['integration', 'test'],
            'audio_duration': 15.0
        }
        
        echo = db_service.create_echo(echo_data)
        
        # Step 4: Verify echo retrieval
        retrieved_echo = db_service.get_echo('test-user', echo.echo_id)
        
        assert retrieved_echo is not None
        assert retrieved_echo.emotion == 'Joy'
        assert retrieved_echo.s3_key == s3_key
        
        # Step 5: Generate playback URL
        playback_url = s3_service.generate_presigned_get_url(s3_key, 'test-user')
        
        assert playback_url
        assert bucket_name in playback_url
        
        # Step 6: Clean up - delete echo and file
        db_service.delete_echo('test-user', echo.echo_id)
        s3_service.delete_audio_file(s3_key, 'test-user')
        
        # Verify cleanup
        deleted_echo = db_service.get_echo('test-user', echo.echo_id)
        assert deleted_echo is None


# Configuration for pytest
@pytest.mark.integration
class TestConfiguration:
    """Test configuration and environment setup"""
    
    def test_service_configuration_validation(self):
        """Test service configuration validation"""
        # Test missing configuration
        with pytest.raises((ValueError, Exception)):
            S3Config(bucket_name=None)
        
        # Test valid configuration
        config = S3Config(bucket_name='test-bucket')
        assert config.bucket_name == 'test-bucket'
        assert config.region == 'us-east-1'  # Default
    
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_environment_variables(self):
        """Test behavior with missing environment variables"""
        # Should use defaults or raise appropriate errors
        config = S3Config(bucket_name='test-bucket')
        assert config.bucket_name == 'test-bucket'