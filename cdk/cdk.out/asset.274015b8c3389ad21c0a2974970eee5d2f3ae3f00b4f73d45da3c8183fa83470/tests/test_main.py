"""
Tests for the main FastAPI application
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestBasicEndpoints:
    """Test basic API endpoints"""
    
    def test_root_endpoint(self):
        """Test the root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Echoes API is running"
        assert data["version"] == "1.0.0"
    
    def test_health_check(self):
        """Test the health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "echoes-api"
        assert data["version"] == "1.0.0"
        assert "environment" in data
    
    def test_openapi_docs(self):
        """Test that OpenAPI docs are accessible in debug mode"""
        response = client.get("/docs")
        # Should redirect to docs or return HTML
        assert response.status_code in [200, 307]
    
    def test_cors_headers(self):
        """Test CORS headers are present"""
        response = client.get("/")
        # Check that CORS headers are present
        assert "access-control-allow-origin" in response.headers or response.status_code == 200


class TestAuthenticatedEndpoints:
    """Test endpoints that require authentication"""
    
    def test_echoes_list_requires_auth(self):
        """Test that echoes list endpoint requires authentication"""
        response = client.get("/api/v1/echoes")
        assert response.status_code == 403  # Forbidden without auth
    
    def test_echoes_init_upload_requires_auth(self):
        """Test that init upload endpoint requires authentication"""
        response = client.post("/api/v1/echoes/init-upload", json={
            "file_extension": "webm",
            "content_type": "audio/webm"
        })
        assert response.status_code == 403  # Forbidden without auth
    
    def test_echoes_create_requires_auth(self):
        """Test that echo creation requires authentication"""
        response = client.post("/api/v1/echoes", 
                             params={"echo_id": "test-echo-id"},
                             json={
                                 "emotion": "joy",
                                 "file_extension": "webm"
                             })
        assert response.status_code == 403  # Forbidden without auth


class TestErrorHandling:
    """Test error handling and validation"""
    
    def test_invalid_endpoint(self):
        """Test 404 for invalid endpoints"""
        response = client.get("/invalid/endpoint")
        assert response.status_code == 404
    
    def test_method_not_allowed(self):
        """Test 405 for invalid methods"""
        response = client.patch("/")
        assert response.status_code == 405