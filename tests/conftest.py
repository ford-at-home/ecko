"""
Pytest configuration and shared fixtures for Echoes test suite.
"""
import pytest
import boto3
import asyncio
from moto import mock_dynamodb, mock_s3
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import tempfile
import os

# Test data constants
TEST_USER_ID = "test-user-123"
TEST_ECHO_ID = "test-echo-456"
TEST_AUDIO_CONTENT = b"fake audio content"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_aws_credentials(monkeypatch):
    """Mock AWS credentials for testing."""
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'testing')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'testing')
    monkeypatch.setenv('AWS_SECURITY_TOKEN', 'testing')
    monkeypatch.setenv('AWS_SESSION_TOKEN', 'testing')
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-east-1')

@pytest.fixture
@mock_dynamodb
def dynamodb_table(mock_aws_credentials):
    """Create a mock DynamoDB table for testing."""
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    
    table = dynamodb.create_table(
        TableName='EchoesTable',
        KeySchema=[
            {'AttributeName': 'userId', 'KeyType': 'HASH'},
            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'userId', 'AttributeType': 'S'},
            {'AttributeName': 'timestamp', 'AttributeType': 'S'},
            {'AttributeName': 'emotion', 'AttributeType': 'S'}
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'emotion-timestamp-index',
                'KeySchema': [
                    {'AttributeName': 'emotion', 'KeyType': 'HASH'},
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'},
                'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
            }
        ],
        BillingMode='PROVISIONED',
        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    )
    
    table.wait_until_exists()
    return table

@pytest.fixture
@mock_s3
def s3_bucket(mock_aws_credentials):
    """Create a mock S3 bucket for testing."""
    s3 = boto3.resource('s3', region_name='us-east-1')
    bucket = s3.create_bucket(Bucket='echoes-audio-test')
    return bucket

@pytest.fixture
def sample_echo_data():
    """Sample echo data for testing."""
    return {
        "userId": TEST_USER_ID,
        "echoId": TEST_ECHO_ID,
        "emotion": "joy",
        "timestamp": "2025-06-25T15:00:00Z",
        "s3Url": f"s3://echoes-audio-test/{TEST_USER_ID}/{TEST_ECHO_ID}.wav",
        "location": {
            "lat": 37.5407,
            "lng": -77.4360
        },
        "tags": ["test", "sample"],
        "transcript": "Test audio transcript",
        "detectedMood": "happy"
    }

@pytest.fixture
def mock_cognito_client():
    """Mock Cognito client for authentication testing."""
    with patch('boto3.client') as mock_client:
        cognito_mock = Mock()
        mock_client.return_value = cognito_mock
        
        # Mock successful authentication
        cognito_mock.admin_initiate_auth.return_value = {
            'AuthenticationResult': {
                'AccessToken': 'test-access-token',
                'IdToken': 'test-id-token',
                'RefreshToken': 'test-refresh-token'
            }
        }
        
        yield cognito_mock

@pytest.fixture
def temp_audio_file():
    """Create a temporary audio file for testing."""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        f.write(TEST_AUDIO_CONTENT)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)

@pytest.fixture
def api_client():
    """FastAPI test client - will be imported when API is implemented."""
    # This will be updated when the actual FastAPI app is created
    from app.main import app  # Placeholder import
    return TestClient(app)

# Performance testing fixtures
@pytest.fixture
def performance_config():
    """Configuration for performance tests."""
    return {
        'max_response_time': 2.0,  # seconds
        'concurrent_users': 10,
        'test_duration': 30,  # seconds
        'upload_timeout': 30,  # seconds
        'large_file_size': 10 * 1024 * 1024,  # 10MB
    }

# Security testing fixtures
@pytest.fixture
def security_config():
    """Configuration for security tests."""
    return {
        'sql_injection_payloads': [
            "'; DROP TABLE EchoesTable; --",
            "' OR '1'='1",
            "UNION SELECT * FROM EchoesTable",
        ],
        'xss_payloads': [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
        ],
        'invalid_tokens': [
            "invalid-token",
            "expired-token",
            "",
            None,
        ]
    }