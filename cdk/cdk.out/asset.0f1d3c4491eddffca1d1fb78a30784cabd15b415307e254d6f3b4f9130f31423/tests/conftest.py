"""
Test configuration and fixtures
"""
import pytest
import os
from unittest.mock import Mock, patch
import sys
from pathlib import Path

# Add the app directory to Python path
app_dir = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(app_dir))

# Set test environment variables
os.environ.update({
    "DEBUG": "true",
    "ENVIRONMENT": "test",
    "AWS_ACCESS_KEY_ID": "test-key",
    "AWS_SECRET_ACCESS_KEY": "test-secret",
    "AWS_REGION": "us-east-1",
    "S3_BUCKET_NAME": "test-bucket",
    "DYNAMODB_TABLE_NAME": "TestEchoesTable",
    "DYNAMODB_ENDPOINT_URL": "http://localhost:8001",
    "COGNITO_USER_POOL_ID": "test-pool",
    "COGNITO_CLIENT_ID": "test-client",
    "JWT_SECRET_KEY": "test-secret-key"
})


@pytest.fixture
def mock_s3_service():
    """Mock S3 service for testing"""
    with patch('app.services.s3_service.S3Service') as mock:
        mock_instance = Mock()
        mock_instance.generate_presigned_upload_url.return_value = {
            "upload_url": "https://test-bucket.s3.amazonaws.com/test/upload",
            "echo_id": "test-echo-id",
            "s3_key": "test-user/test-echo-id.webm",
            "expires_in": 3600
        }
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_dynamodb_service():
    """Mock DynamoDB service for testing"""
    with patch('app.services.dynamodb_service.DynamoDBService') as mock:
        mock_instance = Mock()
        mock_instance.create_echo.return_value = Mock()
        mock_instance.list_echoes.return_value = ([], None)
        mock_instance.get_random_echo.return_value = None
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_cognito_service():
    """Mock Cognito service for testing"""
    with patch('app.services.cognito_service.CognitoService') as mock:
        mock_instance = Mock()
        mock_instance.verify_token.return_value = Mock(
            sub="test-user-id",
            email="test@example.com",
            username="testuser",
            cognito_groups=["users"]
        )
        mock_instance.get_user_context.return_value = Mock(
            user_id="test-user-id",
            email="test@example.com",
            username="testuser",
            cognito_sub="test-user-id",
            groups=["users"]
        )
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def auth_headers():
    """Provide authentication headers for testing"""
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def sample_echo_data():
    """Sample echo data for testing"""
    return {
        "emotion": "joy",
        "tags": ["test", "sample"],
        "transcript": "Test audio content",
        "detected_mood": "happy",
        "file_extension": "webm",
        "duration_seconds": 25.5,
        "location": {
            "lat": 37.5407,
            "lng": -77.4360,
            "address": "Test Location"
        }
    }


@pytest.fixture
def sample_presigned_request():
    """Sample presigned URL request"""
    return {
        "file_extension": "webm",
        "content_type": "audio/webm"
    }