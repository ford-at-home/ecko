"""
Comprehensive tests for the enhanced Echo CRUD API
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import json
import uuid

from app.main import app
from app.models.echo import EmotionType, EchoCreate, LocationData
from app.services.echo_service import EchoService, EchoServiceError, EchoNotFoundError, EchoValidationError


@pytest.fixture
def client():
    """Test client fixture"""
    return TestClient(app)


@pytest.fixture
def mock_user_context():
    """Mock authenticated user context"""
    user_context = Mock()
    user_context.user_id = "test-user-123"
    user_context.email = "test@example.com"
    return user_context


@pytest.fixture
def sample_echo_data():
    """Sample echo creation data"""
    return {
        "emotion": "joy",
        "tags": ["river", "kids", "outdoors"],
        "transcript": "Rio laughing and water splashing",
        "detected_mood": "joyful",
        "file_extension": "webm",
        "duration_seconds": 25.5,
        "location": {
            "lat": 37.5407,
            "lng": -77.4360,
            "address": "James River, Richmond, VA"
        }
    }


@pytest.fixture
def sample_echo_response():
    """Sample echo response data"""
    return {
        "echo_id": "test-echo-123",
        "emotion": "joy",
        "timestamp": "2025-06-25T15:00:00Z",
        "s3_url": "s3://echoes-audio/test-user-123/test-echo-123.webm",
        "location": {
            "lat": 37.5407,
            "lng": -77.4360,
            "address": "James River, Richmond, VA"
        },
        "tags": ["river", "kids", "outdoors"],
        "transcript": "Rio laughing and water splashing",
        "detected_mood": "joyful",
        "duration_seconds": 25.5,
        "created_at": "2025-06-25T15:00:00Z"
    }


class TestEchoInitUpload:
    """Test cases for echo upload initialization"""
    
    @patch('app.routers.echoes.get_current_user')
    @patch('app.routers.echoes.echo_service.init_upload')
    async def test_init_upload_success(self, mock_init_upload, mock_get_user, client, mock_user_context):
        """Test successful upload initialization"""
        # Setup mocks
        mock_get_user.return_value = mock_user_context
        mock_init_upload.return_value = {
            "upload_url": "https://s3.amazonaws.com/presigned-url",
            "echo_id": "test-echo-123",
            "s3_key": "test-user-123/test-echo-123.webm",
            "expires_in": 3600
        }
        
        # Make request
        response = client.post(
            "/echoes/init-upload",
            json={
                "file_extension": "webm",
                "content_type": "audio/webm"
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Assertions
        assert response.status_code == 201
        data = response.json()
        assert "upload_url" in data
        assert "echo_id" in data
        assert data["expires_in"] == 3600
    
    @patch('app.routers.echoes.get_current_user')
    @patch('app.routers.echoes.echo_service.init_upload')
    async def test_init_upload_invalid_format(self, mock_init_upload, mock_get_user, client, mock_user_context):
        """Test upload initialization with invalid file format"""
        # Setup mocks
        mock_get_user.return_value = mock_user_context
        mock_init_upload.side_effect = EchoValidationError("Invalid file format")
        
        # Make request
        response = client.post(
            "/echoes/init-upload",
            json={
                "file_extension": "txt",
                "content_type": "text/plain"
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Assertions
        assert response.status_code == 400
        assert "Invalid file format" in response.json()["detail"]


class TestEchoCreate:
    """Test cases for echo creation"""
    
    @patch('app.routers.echoes.get_current_user')
    @patch('app.routers.echoes.echo_service.create_echo')
    async def test_create_echo_success(self, mock_create_echo, mock_get_user, client, mock_user_context, sample_echo_data, sample_echo_response):
        """Test successful echo creation"""
        # Setup mocks
        mock_get_user.return_value = mock_user_context
        mock_create_echo.return_value = sample_echo_response
        
        # Make request
        response = client.post(
            "/echoes?echo_id=test-echo-123",
            json=sample_echo_data,
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Assertions
        assert response.status_code == 201
        data = response.json()
        assert data["echo_id"] == "test-echo-123"
        assert data["emotion"] == "joy"
        assert len(data["tags"]) == 3
    
    @patch('app.routers.echoes.get_current_user')
    @patch('app.routers.echoes.echo_service.create_echo')
    async def test_create_echo_invalid_id(self, mock_create_echo, mock_get_user, client, mock_user_context, sample_echo_data):
        """Test echo creation with invalid echo ID"""
        # Setup mocks
        mock_get_user.return_value = mock_user_context
        mock_create_echo.side_effect = EchoValidationError("Invalid echo_id format")
        
        # Make request
        response = client.post(
            "/echoes?echo_id=invalid-id",
            json=sample_echo_data,
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Assertions
        assert response.status_code == 400
        assert "Invalid echo_id format" in response.json()["detail"]


class TestEchoList:
    """Test cases for echo listing with advanced filtering"""
    
    @patch('app.routers.echoes.get_current_user')
    @patch('app.routers.echoes.echo_service.list_echoes')
    async def test_list_echoes_basic(self, mock_list_echoes, mock_get_user, client, mock_user_context, sample_echo_response):
        """Test basic echo listing"""
        # Setup mocks
        mock_get_user.return_value = mock_user_context
        mock_list_echoes.return_value = {
            "echoes": [sample_echo_response],
            "total_count": 1,
            "page": 1,
            "page_size": 20,
            "has_more": False
        }
        
        # Make request
        response = client.get(
            "/echoes",
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert len(data["echoes"]) == 1
        assert data["total_count"] == 1
        assert data["page"] == 1
    
    @patch('app.routers.echoes.get_current_user')
    @patch('app.routers.echoes.echo_service.list_echoes')
    async def test_list_echoes_with_emotion_filter(self, mock_list_echoes, mock_get_user, client, mock_user_context, sample_echo_response):
        """Test echo listing with emotion filter"""
        # Setup mocks
        mock_get_user.return_value = mock_user_context
        mock_list_echoes.return_value = {
            "echoes": [sample_echo_response],
            "total_count": 1,
            "page": 1,
            "page_size": 20,
            "has_more": False
        }
        
        # Make request
        response = client.get(
            "/echoes?emotion=joy",
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Assertions
        assert response.status_code == 200
        mock_list_echoes.assert_called_once()
        call_args = mock_list_echoes.call_args[1]
        assert call_args["emotion"] == EmotionType.JOY
    
    @patch('app.routers.echoes.get_current_user')
    @patch('app.routers.echoes.echo_service.list_echoes')
    async def test_list_echoes_with_tags_filter(self, mock_list_echoes, mock_get_user, client, mock_user_context, sample_echo_response):
        """Test echo listing with tags filter"""
        # Setup mocks
        mock_get_user.return_value = mock_user_context
        mock_list_echoes.return_value = {
            "echoes": [sample_echo_response],
            "total_count": 1,
            "page": 1,
            "page_size": 20,
            "has_more": False
        }
        
        # Make request
        response = client.get(
            "/echoes?tags=river,kids",
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Assertions
        assert response.status_code == 200
        call_args = mock_list_echoes.call_args[1]
        assert call_args["tags"] == ["river", "kids"]
    
    @patch('app.routers.echoes.get_current_user')
    @patch('app.routers.echoes.echo_service.list_echoes')
    async def test_list_echoes_with_date_filter(self, mock_list_echoes, mock_get_user, client, mock_user_context, sample_echo_response):
        """Test echo listing with date range filter"""
        # Setup mocks
        mock_get_user.return_value = mock_user_context
        mock_list_echoes.return_value = {
            "echoes": [sample_echo_response],
            "total_count": 1,
            "page": 1,
            "page_size": 20,
            "has_more": False
        }
        
        # Make request
        response = client.get(
            "/echoes?start_date=2025-06-01T00:00:00&end_date=2025-06-30T23:59:59",
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Assertions
        assert response.status_code == 200
        call_args = mock_list_echoes.call_args[1]
        assert call_args["start_date"] is not None
        assert call_args["end_date"] is not None
    
    async def test_list_echoes_invalid_date_format(self, client):
        """Test echo listing with invalid date format"""
        response = client.get(
            "/echoes?start_date=invalid-date",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 400
        assert "Invalid start_date format" in response.json()["detail"]


class TestEchoRetrieve:
    """Test cases for individual echo retrieval"""
    
    @patch('app.routers.echoes.get_current_user')
    @patch('app.routers.echoes.echo_service.get_echo')
    async def test_get_echo_success(self, mock_get_echo, mock_get_user, client, mock_user_context, sample_echo_response):
        """Test successful echo retrieval"""
        # Setup mocks
        mock_get_user.return_value = mock_user_context
        mock_get_echo.return_value = sample_echo_response
        
        # Make request
        response = client.get(
            "/echoes/test-echo-123",
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["echo_id"] == "test-echo-123"
    
    @patch('app.routers.echoes.get_current_user')
    @patch('app.routers.echoes.echo_service.get_echo')
    async def test_get_echo_with_download_url(self, mock_get_echo, mock_get_user, client, mock_user_context, sample_echo_response):
        """Test echo retrieval with download URL"""
        # Setup mocks
        mock_get_user.return_value = mock_user_context
        mock_get_echo.return_value = sample_echo_response
        
        # Make request
        response = client.get(
            "/echoes/test-echo-123?include_download_url=true",
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Assertions
        assert response.status_code == 200
        mock_get_echo.assert_called_once()
        call_args = mock_get_echo.call_args[1]
        assert call_args["include_download_url"] is True
    
    @patch('app.routers.echoes.get_current_user')
    @patch('app.routers.echoes.echo_service.get_echo')
    async def test_get_echo_not_found(self, mock_get_echo, mock_get_user, client, mock_user_context):
        """Test echo retrieval when echo not found"""
        # Setup mocks
        mock_get_user.return_value = mock_user_context
        mock_get_echo.side_effect = EchoNotFoundError("Echo not found")
        
        # Make request
        response = client.get(
            "/echoes/nonexistent-echo",
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Assertions
        assert response.status_code == 404
        assert "Echo not found" in response.json()["detail"]


class TestEchoDelete:
    """Test cases for echo deletion"""
    
    @patch('app.routers.echoes.get_current_user')
    @patch('app.routers.echoes.echo_service.delete_echo')
    async def test_delete_echo_success(self, mock_delete_echo, mock_get_user, client, mock_user_context):
        """Test successful echo deletion"""
        # Setup mocks
        mock_get_user.return_value = mock_user_context
        mock_delete_echo.return_value = True
        
        # Make request
        response = client.delete(
            "/echoes/test-echo-123",
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Assertions
        assert response.status_code == 204
        mock_delete_echo.assert_called_once()
        call_args = mock_delete_echo.call_args[1]
        assert call_args["delete_file"] is True  # Default value
    
    @patch('app.routers.echoes.get_current_user')
    @patch('app.routers.echoes.echo_service.delete_echo')
    async def test_delete_echo_without_file(self, mock_delete_echo, mock_get_user, client, mock_user_context):
        """Test echo deletion without removing S3 file"""
        # Setup mocks
        mock_get_user.return_value = mock_user_context
        mock_delete_echo.return_value = True
        
        # Make request
        response = client.delete(
            "/echoes/test-echo-123?delete_file=false",
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Assertions
        assert response.status_code == 204
        call_args = mock_delete_echo.call_args[1]
        assert call_args["delete_file"] is False
    
    @patch('app.routers.echoes.get_current_user')
    @patch('app.routers.echoes.echo_service.delete_echo')
    async def test_delete_echo_not_found(self, mock_delete_echo, mock_get_user, client, mock_user_context):
        """Test echo deletion when echo not found"""
        # Setup mocks
        mock_get_user.return_value = mock_user_context
        mock_delete_echo.side_effect = EchoNotFoundError("Echo not found")
        
        # Make request
        response = client.delete(
            "/echoes/nonexistent-echo",
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Assertions
        assert response.status_code == 404
        assert "Echo not found" in response.json()["detail"]


class TestEchoRandom:
    """Test cases for random echo retrieval"""
    
    @patch('app.routers.echoes.get_current_user')
    @patch('app.routers.echoes.echo_service.get_random_echo')
    async def test_get_random_echo_success(self, mock_get_random, mock_get_user, client, mock_user_context, sample_echo_response):
        """Test successful random echo retrieval"""
        # Setup mocks
        mock_get_user.return_value = mock_user_context
        mock_get_random.return_value = sample_echo_response
        
        # Make request
        response = client.get(
            "/echoes/random",
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "echo_id" in data
    
    @patch('app.routers.echoes.get_current_user')
    @patch('app.routers.echoes.echo_service.get_random_echo')
    async def test_get_random_echo_with_emotion(self, mock_get_random, mock_get_user, client, mock_user_context, sample_echo_response):
        """Test random echo retrieval with emotion filter"""
        # Setup mocks
        mock_get_user.return_value = mock_user_context
        mock_get_random.return_value = sample_echo_response
        
        # Make request
        response = client.get(
            "/echoes/random?emotion=joy",
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Assertions
        assert response.status_code == 200
        call_args = mock_get_random.call_args[1]
        assert call_args["emotion"] == EmotionType.JOY


class TestEchoStatistics:
    """Test cases for echo statistics"""
    
    @patch('app.routers.echoes.get_current_user')
    @patch('app.routers.echoes.echo_service.get_user_statistics')
    async def test_get_statistics_success(self, mock_get_stats, mock_get_user, client, mock_user_context):
        """Test successful statistics retrieval"""
        # Setup mocks
        mock_get_user.return_value = mock_user_context
        mock_get_stats.return_value = {
            "total_echoes": 10,
            "emotion_distribution": {"joy": 5, "calm": 3, "sadness": 2},
            "total_duration_seconds": 250.5,
            "average_duration_seconds": 25.05,
            "oldest_echo_date": "2025-06-01T10:00:00Z",
            "newest_echo_date": "2025-06-25T15:00:00Z",
            "most_common_emotion": "joy"
        }
        
        # Make request
        response = client.get(
            "/echoes/stats",
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["total_echoes"] == 10
        assert data["most_common_emotion"] == "joy"
        assert "emotion_distribution" in data


class TestEchoHealthCheck:
    """Test cases for health check endpoint"""
    
    async def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/echoes/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "echoes"


class TestAuthentication:
    """Test cases for authentication"""
    
    async def test_missing_auth_header(self, client):
        """Test request without authentication header"""
        response = client.get("/echoes")
        
        assert response.status_code == 401
    
    async def test_invalid_token(self, client):
        """Test request with invalid token"""
        with patch('app.routers.echoes.get_current_user') as mock_auth:
            mock_auth.side_effect = HTTPException(status_code=401, detail="Invalid token")
            
            response = client.get(
                "/echoes",
                headers={"Authorization": "Bearer invalid-token"}
            )
            
            assert response.status_code == 401


class TestPagination:
    """Test cases for pagination functionality"""
    
    @patch('app.routers.echoes.get_current_user')
    @patch('app.routers.echoes.echo_service.list_echoes')
    async def test_pagination_parameters(self, mock_list_echoes, mock_get_user, client, mock_user_context):
        """Test pagination parameters are passed correctly"""
        # Setup mocks
        mock_get_user.return_value = mock_user_context
        mock_list_echoes.return_value = {
            "echoes": [],
            "total_count": 0,
            "page": 2,
            "page_size": 10,
            "has_more": False
        }
        
        # Make request
        response = client.get(
            "/echoes?page=2&page_size=10",
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Assertions
        assert response.status_code == 200
        call_args = mock_list_echoes.call_args[1]
        assert call_args["page"] == 2
        assert call_args["page_size"] == 10
    
    async def test_invalid_pagination_parameters(self, client):
        """Test invalid pagination parameters"""
        response = client.get(
            "/echoes?page=0&page_size=101",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 422  # Validation error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])