"""
Unit tests for Echoes API endpoints.
Tests all CRUD operations for the audio time machine functionality.
"""
import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException
import boto3
from moto import mock_dynamodb, mock_s3
import uuid
from datetime import datetime, timezone

class TestEchoesAPI:
    """Test cases for Echoes API endpoints."""
    
    @pytest.mark.asyncio
    async def test_init_upload_success(self, api_client, s3_bucket, mock_cognito_client):
        """Test successful upload initialization."""
        request_data = {
            "userId": "test-user-123",
            "fileType": "audio/wav",
            "fileName": "test-echo.wav"
        }
        
        with patch('app.services.s3_service.generate_presigned_url') as mock_presigned:
            mock_presigned.return_value = "https://s3.amazonaws.com/echoes-audio-test/presigned-url"
            
            response = api_client.post("/echoes/init-upload", json=request_data)
            
            assert response.status_code == 200
            data = response.json()
            assert "uploadUrl" in data
            assert "echoId" in data
            assert data["uploadUrl"].startswith("https://s3.amazonaws.com")
    
    @pytest.mark.asyncio
    async def test_init_upload_invalid_file_type(self, api_client):
        """Test upload initialization with invalid file type."""
        request_data = {
            "userId": "test-user-123",
            "fileType": "text/plain",  # Invalid type
            "fileName": "test.txt"
        }
        
        response = api_client.post("/echoes/init-upload", json=request_data)
        
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_save_echo_success(self, api_client, dynamodb_table, sample_echo_data):
        """Test successful echo metadata save."""
        with patch('app.services.dynamodb_service.save_echo') as mock_save:
            mock_save.return_value = sample_echo_data
            
            response = api_client.post("/echoes", json=sample_echo_data)
            
            assert response.status_code == 201
            data = response.json()
            assert data["echoId"] == sample_echo_data["echoId"]
            assert data["emotion"] == sample_echo_data["emotion"]
    
    @pytest.mark.asyncio
    async def test_save_echo_missing_required_fields(self, api_client):
        """Test echo save with missing required fields."""
        incomplete_data = {
            "userId": "test-user-123",
            # Missing emotion, timestamp, etc.
        }
        
        response = api_client.post("/echoes", json=incomplete_data)
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_get_echoes_by_user(self, api_client, dynamodb_table, sample_echo_data):
        """Test retrieving echoes for a specific user."""
        with patch('app.services.dynamodb_service.get_echoes_by_user') as mock_get:
            mock_get.return_value = [sample_echo_data]
            
            response = api_client.get(f"/echoes?userId={sample_echo_data['userId']}")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["echoes"]) == 1
            assert data["echoes"][0]["userId"] == sample_echo_data["userId"]
    
    @pytest.mark.asyncio
    async def test_get_echoes_with_emotion_filter(self, api_client, dynamodb_table):
        """Test retrieving echoes filtered by emotion."""
        with patch('app.services.dynamodb_service.get_echoes_by_emotion') as mock_get:
            mock_echoes = [
                {"echoId": "1", "emotion": "joy", "userId": "test-user"},
                {"echoId": "2", "emotion": "joy", "userId": "test-user"}
            ]
            mock_get.return_value = mock_echoes
            
            response = api_client.get("/echoes?emotion=joy&userId=test-user")
            
            assert response.status_code == 200
            data = response.json()
            assert all(echo["emotion"] == "joy" for echo in data["echoes"])
    
    @pytest.mark.asyncio
    async def test_get_random_echo_success(self, api_client, sample_echo_data):
        """Test getting a random echo with emotion filter."""
        with patch('app.services.dynamodb_service.get_random_echo') as mock_random:
            mock_random.return_value = sample_echo_data
            
            response = api_client.get("/echoes/random?emotion=joy&userId=test-user-123")
            
            assert response.status_code == 200
            data = response.json()
            assert data["emotion"] == "joy"
            assert data["userId"] == "test-user-123"
    
    @pytest.mark.asyncio
    async def test_get_random_echo_not_found(self, api_client):
        """Test getting random echo when none match criteria."""
        with patch('app.services.dynamodb_service.get_random_echo') as mock_random:
            mock_random.return_value = None
            
            response = api_client.get("/echoes/random?emotion=sadness&userId=test-user-123")
            
            assert response.status_code == 404
            assert "No echoes found" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_delete_echo_success(self, api_client, dynamodb_table):
        """Test successful echo deletion."""
        echo_id = "test-echo-456"
        user_id = "test-user-123"
        
        with patch('app.services.dynamodb_service.delete_echo') as mock_delete:
            mock_delete.return_value = True
            
            response = api_client.delete(f"/echoes/{echo_id}?userId={user_id}")
            
            assert response.status_code == 204
    
    @pytest.mark.asyncio
    async def test_delete_echo_not_found(self, api_client):
        """Test deleting non-existent echo."""
        with patch('app.services.dynamodb_service.delete_echo') as mock_delete:
            mock_delete.return_value = False
            
            response = api_client.delete("/echoes/nonexistent?userId=test-user")
            
            assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_update_echo_success(self, api_client, sample_echo_data):
        """Test successful echo update."""
        update_data = {
            "tags": ["updated", "test"],
            "transcript": "Updated transcript"
        }
        
        with patch('app.services.dynamodb_service.update_echo') as mock_update:
            updated_echo = {**sample_echo_data, **update_data}
            mock_update.return_value = updated_echo
            
            response = api_client.put(f"/echoes/{sample_echo_data['echoId']}", json=update_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["tags"] == update_data["tags"]
            assert data["transcript"] == update_data["transcript"]


class TestAuthenticationEndpoints:
    """Test cases for authentication endpoints."""
    
    @pytest.mark.asyncio
    async def test_login_success(self, api_client, mock_cognito_client):
        """Test successful user login."""
        login_data = {
            "username": "testuser@example.com",
            "password": "SecurePassword123!"
        }
        
        response = api_client.post("/auth/login", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "accessToken" in data
        assert "idToken" in data
        assert "refreshToken" in data
    
    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, api_client):
        """Test login with invalid credentials."""
        with patch('app.services.auth_service.authenticate_user') as mock_auth:
            mock_auth.side_effect = HTTPException(status_code=401, detail="Invalid credentials")
            
            login_data = {
                "username": "testuser@example.com",
                "password": "wrongpassword"
            }
            
            response = api_client.post("/auth/login", json=login_data)
            
            assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_refresh_token_success(self, api_client, mock_cognito_client):
        """Test successful token refresh."""
        refresh_data = {
            "refreshToken": "valid-refresh-token"
        }
        
        with patch('app.services.auth_service.refresh_access_token') as mock_refresh:
            mock_refresh.return_value = {
                "accessToken": "new-access-token",
                "idToken": "new-id-token"
            }
            
            response = api_client.post("/auth/refresh", json=refresh_data)
            
            assert response.status_code == 200
            data = response.json()
            assert "accessToken" in data
            assert "idToken" in data
    
    @pytest.mark.asyncio
    async def test_logout_success(self, api_client):
        """Test successful user logout."""
        headers = {"Authorization": "Bearer valid-access-token"}
        
        with patch('app.services.auth_service.logout_user') as mock_logout:
            mock_logout.return_value = True
            
            response = api_client.post("/auth/logout", headers=headers)
            
            assert response.status_code == 200


class TestErrorHandling:
    """Test cases for API error handling."""
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, api_client):
        """Test API rate limiting."""
        # Simulate multiple rapid requests
        with patch('app.middleware.rate_limiter.is_allowed') as mock_limiter:
            mock_limiter.return_value = False
            
            response = api_client.get("/echoes?userId=test-user")
            
            assert response.status_code == 429
            assert "Rate limit exceeded" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_cors_headers(self, api_client):
        """Test CORS headers are properly set."""
        response = api_client.options("/echoes")
        
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Methods" in response.headers
    
    @pytest.mark.asyncio
    async def test_internal_server_error_handling(self, api_client):
        """Test proper handling of internal server errors."""
        with patch('app.services.dynamodb_service.get_echoes_by_user') as mock_get:
            mock_get.side_effect = Exception("Database connection error")
            
            response = api_client.get("/echoes?userId=test-user")
            
            assert response.status_code == 500
            # Ensure error details are not leaked in production
            assert "Database connection error" not in response.json()["detail"]


class TestValidation:
    """Test cases for input validation."""
    
    @pytest.mark.parametrize("invalid_emotion", [
        "",
        "invalid_emotion_with_underscores",
        "VeryLongEmotionNameThatExceedsMaxLength",
        123,
        None
    ])
    @pytest.mark.asyncio
    async def test_invalid_emotion_validation(self, api_client, invalid_emotion):
        """Test validation of emotion field."""
        echo_data = {
            "userId": "test-user-123",
            "echoId": "test-echo-456",
            "emotion": invalid_emotion,
            "timestamp": "2025-06-25T15:00:00Z"
        }
        
        response = api_client.post("/echoes", json=echo_data)
        
        assert response.status_code == 422
    
    @pytest.mark.parametrize("invalid_coordinates", [
        {"lat": 91, "lng": 0},  # Invalid latitude
        {"lat": 0, "lng": 181},  # Invalid longitude
        {"lat": "invalid", "lng": 0},  # Non-numeric
        {"lat": 0},  # Missing longitude
    ])
    @pytest.mark.asyncio
    async def test_invalid_location_validation(self, api_client, invalid_coordinates):
        """Test validation of location coordinates."""
        echo_data = {
            "userId": "test-user-123",
            "echoId": "test-echo-456",
            "emotion": "joy",
            "timestamp": "2025-06-25T15:00:00Z",
            "location": invalid_coordinates
        }
        
        response = api_client.post("/echoes", json=echo_data)
        
        assert response.status_code == 422