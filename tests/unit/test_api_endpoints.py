"""
Unit tests for Echoes API endpoints
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from fastapi import HTTPException

from backend.src.main import app
from backend.src.services.auth_service import UserInfo


# Test client
client = TestClient(app)


class TestHealthEndpoint:
    """Test cases for health check endpoint"""
    
    def test_health_check_success(self):
        """Test successful health check"""
        with patch('backend.src.services.s3_service.s3_service.health_check') as mock_s3, \
             patch('backend.src.services.dynamodb_service.dynamodb_service.health_check') as mock_db, \
             patch('backend.src.services.auth_service.auth_service.health_check') as mock_auth:
            
            mock_s3.return_value = {'status': 'healthy'}
            mock_db.return_value = {'status': 'healthy'}
            mock_auth.return_value = {'status': 'healthy'}
            
            response = client.get('/health')
            
            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'healthy'
            assert 'services' in data
            assert data['services']['s3']['status'] == 'healthy'
    
    def test_health_check_degraded(self):
        """Test health check with degraded service"""
        with patch('backend.src.services.s3_service.s3_service.health_check') as mock_s3, \
             patch('backend.src.services.dynamodb_service.dynamodb_service.health_check') as mock_db, \
             patch('backend.src.services.auth_service.auth_service.health_check') as mock_auth:
            
            mock_s3.return_value = {'status': 'unhealthy', 'error': 'Connection failed'}
            mock_db.return_value = {'status': 'healthy'}
            mock_auth.return_value = {'status': 'healthy'}
            
            response = client.get('/health')
            
            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'degraded'


class TestRootEndpoint:
    """Test cases for root endpoint"""
    
    def test_root_endpoint(self):
        """Test root endpoint response"""
        response = client.get('/')
        
        assert response.status_code == 200
        data = response.json()
        assert 'message' in data
        assert 'Welcome to Echoes API' in data['message']
        assert data['version'] == '1.0.0'


class TestAuthenticationDependency:
    """Test cases for authentication dependency"""
    
    def test_missing_authorization_header(self):
        """Test request without authorization header"""
        response = client.post('/echoes/init-upload', json={})
        
        assert response.status_code == 403  # FastAPI returns 403 for missing auth


class TestInitUploadEndpoint:
    """Test cases for upload initialization endpoint"""
    
    def get_mock_user(self):
        """Get mock user for testing"""
        return UserInfo(
            user_id='test-user-123',
            username='testuser',
            email='test@example.com',
            email_verified=True
        )
    
    def get_auth_headers(self):
        """Get mock authorization headers"""
        return {'Authorization': 'Bearer mock-token'}
    
    @patch('backend.src.api.echoes.get_current_user')
    @patch('backend.src.services.s3_service.s3_service.generate_presigned_post')
    def test_init_upload_success(self, mock_s3_presigned, mock_get_user):
        """Test successful upload initialization"""
        # Mock user authentication
        mock_get_user.return_value = self.get_mock_user()
        
        # Mock S3 presigned URL response
        mock_s3_response = Mock()
        mock_s3_response.upload_url = 'https://s3.amazonaws.com/bucket'
        mock_s3_response.fields = {'key': 'test-key', 'policy': 'test-policy'}
        mock_s3_response.key = 'test-user-123/Joy/echo-id_20240101_120000.webm'
        mock_s3_response.expires_at = datetime.utcnow() + timedelta(hours=1)
        mock_s3_response.max_file_size = 50 * 1024 * 1024
        mock_s3_presigned.return_value = mock_s3_response
        
        request_data = {
            'content_type': 'audio/webm',
            'file_size': 1024000,
            'emotion': 'Joy',
            'tags': ['nature', 'peaceful']
        }
        
        response = client.post(
            '/echoes/init-upload',
            json=request_data,
            headers=self.get_auth_headers()
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'upload_url' in data
        assert 'fields' in data
        assert 'echo_id' in data
        assert data['upload_url'] == 'https://s3.amazonaws.com/bucket'
    
    @patch('backend.src.api.echoes.get_current_user')
    def test_init_upload_invalid_content_type(self, mock_get_user):
        """Test upload initialization with invalid content type"""
        mock_get_user.return_value = self.get_mock_user()
        
        request_data = {
            'content_type': 'video/mp4',  # Invalid for audio
            'file_size': 1024000,
            'emotion': 'Joy'
        }
        
        response = client.post(
            '/echoes/init-upload',
            json=request_data,
            headers=self.get_auth_headers()
        )
        
        assert response.status_code == 400
    
    @patch('backend.src.api.echoes.get_current_user')
    def test_init_upload_missing_emotion(self, mock_get_user):
        """Test upload initialization without emotion"""
        mock_get_user.return_value = self.get_mock_user()
        
        request_data = {
            'content_type': 'audio/webm',
            'file_size': 1024000
            # Missing emotion
        }
        
        response = client.post(
            '/echoes/init-upload',
            json=request_data,
            headers=self.get_auth_headers()
        )
        
        assert response.status_code == 422  # Pydantic validation error


class TestCreateEchoEndpoint:
    """Test cases for create echo endpoint"""
    
    def get_mock_user(self):
        """Get mock user for testing"""
        return UserInfo(
            user_id='test-user-123',
            username='testuser',
            email='test@example.com'
        )
    
    def get_auth_headers(self):
        """Get mock authorization headers"""
        return {'Authorization': 'Bearer mock-token'}
    
    @patch('backend.src.api.echoes.get_current_user')
    @patch('backend.src.services.s3_service.s3_service.get_file_metadata')
    @patch('backend.src.services.dynamodb_service.dynamodb_service.create_echo')
    @patch('backend.src.services.s3_service.s3_service.generate_presigned_get_url')
    def test_create_echo_success(self, mock_s3_get_url, mock_db_create, mock_s3_metadata, mock_get_user):
        """Test successful echo creation"""
        # Mock dependencies
        mock_get_user.return_value = self.get_mock_user()
        mock_s3_metadata.return_value = {
            'size': 1024000,
            'content_type': 'audio/webm'
        }
        
        # Mock DynamoDB response
        mock_echo = Mock()
        mock_echo.echo_id = 'echo-123'
        mock_echo.emotion = 'Joy'
        mock_echo.timestamp = '2024-01-01T12:00:00Z'
        mock_echo.location = None
        mock_echo.tags = ['nature']
        mock_echo.transcript = ''
        mock_echo.detected_mood = None
        mock_echo.audio_duration = 15.0
        mock_echo.created_at = '2024-01-01T12:00:00Z'
        mock_db_create.return_value = mock_echo
        
        mock_s3_get_url.return_value = 'https://s3.amazonaws.com/presigned-url'
        
        request_data = {
            's3_key': 'test-user-123/Joy/echo-123.webm',
            'emotion': 'Joy',
            'tags': ['nature'],
            'transcript': 'Birds singing'
        }
        
        response = client.post(
            '/echoes',
            json=request_data,
            headers=self.get_auth_headers()
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['echo_id'] == 'echo-123'
        assert data['emotion'] == 'Joy'
        assert 'playback_url' in data
    
    @patch('backend.src.api.echoes.get_current_user')
    def test_create_echo_unauthorized_s3_key(self, mock_get_user):
        """Test echo creation with unauthorized S3 key"""
        mock_get_user.return_value = self.get_mock_user()
        
        request_data = {
            's3_key': 'other-user/Joy/echo-123.webm',  # Different user
            'emotion': 'Joy'
        }
        
        response = client.post(
            '/echoes',
            json=request_data,
            headers=self.get_auth_headers()
        )
        
        assert response.status_code == 403
        assert 'Unauthorized access' in response.json()['detail']
    
    @patch('backend.src.api.echoes.get_current_user')
    @patch('backend.src.services.s3_service.s3_service.get_file_metadata')
    def test_create_echo_file_not_found(self, mock_s3_metadata, mock_get_user):
        """Test echo creation with non-existent file"""
        mock_get_user.return_value = self.get_mock_user()
        mock_s3_metadata.return_value = None  # File not found
        
        request_data = {
            's3_key': 'test-user-123/Joy/nonexistent.webm',
            'emotion': 'Joy'
        }
        
        response = client.post(
            '/echoes',
            json=request_data,
            headers=self.get_auth_headers()
        )
        
        assert response.status_code == 404
        assert 'Audio file not found' in response.json()['detail']


class TestListEchoesEndpoint:
    """Test cases for list echoes endpoint"""
    
    def get_mock_user(self):
        """Get mock user for testing"""
        return UserInfo(
            user_id='test-user-123',
            username='testuser',
            email='test@example.com'
        )
    
    def get_auth_headers(self):
        """Get mock authorization headers"""
        return {'Authorization': 'Bearer mock-token'}
    
    @patch('backend.src.api.echoes.get_current_user')
    @patch('backend.src.services.dynamodb_service.dynamodb_service.list_user_echoes')
    @patch('backend.src.services.s3_service.s3_service.generate_presigned_get_url')
    def test_list_echoes_success(self, mock_s3_url, mock_db_list, mock_get_user):
        """Test successful echo listing"""
        mock_get_user.return_value = self.get_mock_user()
        
        # Mock database response
        mock_db_list.return_value = {
            'echoes': [
                {
                    'echo_id': 'echo-1',
                    'emotion': 'Joy',
                    'timestamp': '2024-01-01T12:00:00Z',
                    's3_key': 'test-user-123/Joy/echo-1.webm',
                    'tags': ['nature'],
                    'transcript': '',
                    'detected_mood': None,
                    'audio_duration': 15.0,
                    'created_at': '2024-01-01T12:00:00Z'
                }
            ],
            'count': 1,
            'last_evaluated_key': None
        }
        
        mock_s3_url.return_value = 'https://s3.amazonaws.com/presigned-url'
        
        response = client.get('/echoes', headers=self.get_auth_headers())
        
        assert response.status_code == 200
        data = response.json()
        assert data['count'] == 1
        assert len(data['echoes']) == 1
        assert data['echoes'][0]['echo_id'] == 'echo-1'
    
    @patch('backend.src.api.echoes.get_current_user')
    @patch('backend.src.services.dynamodb_service.dynamodb_service.filter_echoes_by_emotion')
    @patch('backend.src.services.s3_service.s3_service.generate_presigned_get_url')
    def test_list_echoes_with_emotion_filter(self, mock_s3_url, mock_db_filter, mock_get_user):
        """Test echo listing with emotion filter"""
        mock_get_user.return_value = self.get_mock_user()
        
        # Mock filtered results
        mock_echo = Mock()
        mock_echo.echo_id = 'echo-1'
        mock_echo.emotion = 'Calm'
        mock_echo.timestamp = '2024-01-01T12:00:00Z'
        mock_echo.s3_key = 'test-user-123/Calm/echo-1.webm'
        mock_echo.location = None
        mock_echo.tags = ['meditation']
        mock_echo.transcript = ''
        mock_echo.detected_mood = None
        mock_echo.audio_duration = 20.0
        mock_echo.created_at = '2024-01-01T12:00:00Z'
        
        mock_db_filter.return_value = [mock_echo]
        mock_s3_url.return_value = 'https://s3.amazonaws.com/presigned-url'
        
        response = client.get('/echoes?emotion=Calm', headers=self.get_auth_headers())
        
        assert response.status_code == 200
        data = response.json()
        assert data['count'] == 1
        assert data['echoes'][0]['emotion'] == 'Calm'


class TestRandomEchoEndpoint:
    """Test cases for random echo endpoint"""
    
    def get_mock_user(self):
        """Get mock user for testing"""
        return UserInfo(
            user_id='test-user-123',
            username='testuser',
            email='test@example.com'
        )
    
    def get_auth_headers(self):
        """Get mock authorization headers"""
        return {'Authorization': 'Bearer mock-token'}
    
    @patch('backend.src.api.echoes.get_current_user')
    @patch('backend.src.services.dynamodb_service.dynamodb_service.get_random_echo_by_emotion')
    @patch('backend.src.services.s3_service.s3_service.generate_presigned_get_url')
    def test_get_random_echo_success(self, mock_s3_url, mock_db_random, mock_get_user):
        """Test successful random echo retrieval"""
        mock_get_user.return_value = self.get_mock_user()
        
        # Mock random echo
        mock_echo = Mock()
        mock_echo.echo_id = 'random-echo-1'
        mock_echo.emotion = 'Joy'
        mock_echo.timestamp = '2024-01-01T12:00:00Z'
        mock_echo.s3_key = 'test-user-123/Joy/random-echo-1.webm'
        mock_echo.location = None
        mock_echo.tags = ['surprise']
        mock_echo.transcript = ''
        mock_echo.detected_mood = None
        mock_echo.audio_duration = 12.0
        mock_echo.created_at = '2024-01-01T12:00:00Z'
        
        mock_db_random.return_value = mock_echo
        mock_s3_url.return_value = 'https://s3.amazonaws.com/presigned-url'
        
        response = client.get('/echoes/random?emotion=Joy', headers=self.get_auth_headers())
        
        assert response.status_code == 200
        data = response.json()
        assert data['echo_id'] == 'random-echo-1'
        assert data['emotion'] == 'Joy'
    
    @patch('backend.src.api.echoes.get_current_user')
    @patch('backend.src.services.dynamodb_service.dynamodb_service.get_random_echo_by_emotion')
    def test_get_random_echo_not_found(self, mock_db_random, mock_get_user):
        """Test random echo when none found"""
        mock_get_user.return_value = self.get_mock_user()
        mock_db_random.return_value = None
        
        response = client.get('/echoes/random?emotion=Sadness', headers=self.get_auth_headers())
        
        assert response.status_code == 404
        assert 'No echoes found' in response.json()['detail']


class TestGetEchoEndpoint:
    """Test cases for get specific echo endpoint"""
    
    def get_mock_user(self):
        """Get mock user for testing"""
        return UserInfo(
            user_id='test-user-123',
            username='testuser',
            email='test@example.com'
        )
    
    def get_auth_headers(self):
        """Get mock authorization headers"""
        return {'Authorization': 'Bearer mock-token'}
    
    @patch('backend.src.api.echoes.get_current_user')
    @patch('backend.src.services.dynamodb_service.dynamodb_service.get_echo')
    @patch('backend.src.services.s3_service.s3_service.generate_presigned_get_url')
    def test_get_echo_success(self, mock_s3_url, mock_db_get, mock_get_user):
        """Test successful echo retrieval"""
        mock_get_user.return_value = self.get_mock_user()
        
        # Mock echo
        mock_echo = Mock()
        mock_echo.echo_id = 'specific-echo'
        mock_echo.emotion = 'Peaceful'
        mock_echo.timestamp = '2024-01-01T12:00:00Z'
        mock_echo.s3_key = 'test-user-123/Peaceful/specific-echo.webm'
        mock_echo.location = None
        mock_echo.tags = ['sunset']
        mock_echo.transcript = 'Ocean waves'
        mock_echo.detected_mood = None
        mock_echo.audio_duration = 25.0
        mock_echo.created_at = '2024-01-01T12:00:00Z'
        
        mock_db_get.return_value = mock_echo
        mock_s3_url.return_value = 'https://s3.amazonaws.com/presigned-url'
        
        response = client.get('/echoes/specific-echo', headers=self.get_auth_headers())
        
        assert response.status_code == 200
        data = response.json()
        assert data['echo_id'] == 'specific-echo'
        assert data['emotion'] == 'Peaceful'
        assert data['transcript'] == 'Ocean waves'
    
    @patch('backend.src.api.echoes.get_current_user')
    @patch('backend.src.services.dynamodb_service.dynamodb_service.get_echo')
    def test_get_echo_not_found(self, mock_db_get, mock_get_user):
        """Test echo retrieval when not found"""
        mock_get_user.return_value = self.get_mock_user()
        mock_db_get.return_value = None
        
        response = client.get('/echoes/nonexistent', headers=self.get_auth_headers())
        
        assert response.status_code == 404
        assert 'Echo not found' in response.json()['detail']


class TestDeleteEchoEndpoint:
    """Test cases for delete echo endpoint"""
    
    def get_mock_user(self):
        """Get mock user for testing"""
        return UserInfo(
            user_id='test-user-123',
            username='testuser',
            email='test@example.com'
        )
    
    def get_auth_headers(self):
        """Get mock authorization headers"""
        return {'Authorization': 'Bearer mock-token'}
    
    @patch('backend.src.api.echoes.get_current_user')
    @patch('backend.src.services.dynamodb_service.dynamodb_service.get_echo')
    @patch('backend.src.services.s3_service.s3_service.delete_audio_file')
    @patch('backend.src.services.dynamodb_service.dynamodb_service.delete_echo')
    def test_delete_echo_success(self, mock_db_delete, mock_s3_delete, mock_db_get, mock_get_user):
        """Test successful echo deletion"""
        mock_get_user.return_value = self.get_mock_user()
        
        # Mock echo to delete
        mock_echo = Mock()
        mock_echo.echo_id = 'echo-to-delete'
        mock_echo.s3_key = 'test-user-123/Joy/echo-to-delete.webm'
        mock_db_get.return_value = mock_echo
        
        mock_s3_delete.return_value = True
        mock_db_delete.return_value = True
        
        response = client.delete('/echoes/echo-to-delete', headers=self.get_auth_headers())
        
        assert response.status_code == 200
        data = response.json()
        assert 'deleted successfully' in data['message']
        assert data['echo_id'] == 'echo-to-delete'
    
    @patch('backend.src.api.echoes.get_current_user')
    @patch('backend.src.services.dynamodb_service.dynamodb_service.get_echo')
    def test_delete_echo_not_found(self, mock_db_get, mock_get_user):
        """Test deletion of non-existent echo"""
        mock_get_user.return_value = self.get_mock_user()
        mock_db_get.return_value = None
        
        response = client.delete('/echoes/nonexistent', headers=self.get_auth_headers())
        
        assert response.status_code == 404
        assert 'Echo not found' in response.json()['detail']


class TestUserStatsEndpoint:
    """Test cases for user statistics endpoint"""
    
    def get_mock_user(self):
        """Get mock user for testing"""
        return UserInfo(
            user_id='test-user-123',
            username='testuser',
            email='test@example.com'
        )
    
    def get_auth_headers(self):
        """Get mock authorization headers"""
        return {'Authorization': 'Bearer mock-token'}
    
    @patch('backend.src.api.echoes.get_current_user')
    @patch('backend.src.services.dynamodb_service.dynamodb_service.get_user_stats')
    def test_get_user_stats_success(self, mock_db_stats, mock_get_user):
        """Test successful user statistics retrieval"""
        user = self.get_mock_user()
        mock_get_user.return_value = user
        
        mock_stats = {
            'total_echoes': 15,
            'total_duration_seconds': 300.0,
            'emotions_breakdown': {
                'Joy': 5,
                'Calm': 4,
                'Peaceful': 3,
                'Excited': 2,
                'Grateful': 1
            },
            'most_common_emotion': 'Joy'
        }
        mock_db_stats.return_value = mock_stats
        
        response = client.get('/echoes/stats/user', headers=self.get_auth_headers())
        
        assert response.status_code == 200
        data = response.json()
        assert data['user_id'] == user.user_id
        assert data['username'] == user.username
        assert data['stats']['total_echoes'] == 15
        assert data['stats']['most_common_emotion'] == 'Joy'


class TestProcessUploadEndpoint:
    """Test cases for direct file upload processing"""
    
    def get_mock_user(self):
        """Get mock user for testing"""
        return UserInfo(
            user_id='test-user-123',
            username='testuser',
            email='test@example.com'
        )
    
    def get_auth_headers(self):
        """Get mock authorization headers"""
        return {'Authorization': 'Bearer mock-token'}
    
    @patch('backend.src.api.echoes.get_current_user')
    @patch('backend.src.services.audio_processor.audio_processor.validate_and_process')
    def test_process_upload_success(self, mock_process, mock_get_user):
        """Test successful file upload processing"""
        mock_get_user.return_value = self.get_mock_user()
        
        mock_process.return_value = {
            'success': True,
            'metadata': {
                'duration': 15.0,
                'sample_rate': 44100,
                'channels': 2,
                'format': '.wav',
                'valid': True
            },
            'processing_applied': True
        }
        
        # Create fake file data
        file_data = b'fake audio file content'
        
        response = client.post(
            '/echoes/process-upload',
            files={'file': ('test.wav', file_data, 'audio/wav')},
            headers=self.get_auth_headers()
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'processed successfully' in data['message']
        assert data['processing_applied'] is True
    
    @patch('backend.src.api.echoes.get_current_user')
    @patch('backend.src.services.audio_processor.audio_processor.validate_and_process')
    def test_process_upload_invalid_file(self, mock_process, mock_get_user):
        """Test file upload processing with invalid file"""
        mock_get_user.return_value = self.get_mock_user()
        
        mock_process.return_value = {
            'success': False,
            'error': 'Invalid audio format',
            'metadata': None
        }
        
        file_data = b'invalid file content'
        
        response = client.post(
            '/echoes/process-upload',
            files={'file': ('test.txt', file_data, 'text/plain')},
            headers=self.get_auth_headers()
        )
        
        assert response.status_code == 400
        assert 'Invalid audio format' in response.json()['detail']


@pytest.fixture
def mock_auth_dependency():
    """Fixture to mock authentication dependency"""
    with patch('backend.src.api.echoes.get_current_user') as mock:
        mock.return_value = UserInfo(
            user_id='test-user',
            username='testuser',
            email='test@example.com'
        )
        yield mock


class TestAPIIntegration:
    """Integration tests for API endpoints"""
    
    def test_cors_headers(self):
        """Test CORS headers are present"""
        response = client.options('/echoes/init-upload')
        
        # Should have CORS headers
        assert 'access-control-allow-origin' in response.headers
        assert 'access-control-allow-methods' in response.headers
    
    def test_error_handling_format(self):
        """Test error response format consistency"""
        # Test 404 error format
        response = client.get('/nonexistent-endpoint')
        
        assert response.status_code == 404
        data = response.json()
        assert 'detail' in data
    
    @patch('backend.src.services.s3_service.s3_service.health_check')
    def test_service_unavailable_handling(self, mock_s3_health):
        """Test handling when services are unavailable"""
        mock_s3_health.side_effect = Exception("Service unavailable")
        
        response = client.get('/health')
        
        assert response.status_code == 503
        data = response.json()
        assert data['status'] == 'unhealthy'


# Pytest configuration
@pytest.mark.asyncio
class TestAsyncEndpoints:
    """Test async functionality if any endpoints use async"""
    
    async def test_async_functionality(self):
        """Test async endpoint functionality"""
        # This would test any async endpoints
        # Currently most endpoints are sync but this provides structure
        pass