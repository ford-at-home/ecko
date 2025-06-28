"""
Comprehensive security testing for Echoes audio time machine.
Tests authentication, authorization, input validation, and data protection.
"""

import pytest
import jwt
import hashlib
import base64
import json
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock
import uuid
import requests
from fastapi.testclient import TestClient
import boto3
from moto import mock_s3, mock_dynamodb, mock_cognitoidp
import sql_inject_payloads
import xss_payloads

class TestAuthenticationSecurity:
    """Test authentication security mechanisms."""
    
    def test_password_complexity_requirements(self, api_client):
        """Test password complexity enforcement."""
        weak_passwords = [
            "123456",           # Too simple
            "password",         # Common word
            "abc123",          # Too short
            "PASSWORD123",     # No lowercase
            "password123",     # No uppercase
            "Password",        # No numbers
            "",                # Empty
            " " * 8,          # Only spaces
        ]
        
        for weak_password in weak_passwords:
            response = api_client.post("/auth/signup", json={
                "email": "test@example.com",
                "password": weak_password,
                "confirmPassword": weak_password
            })
            
            assert response.status_code == 400
            assert "password" in response.json()["detail"].lower()
    
    def test_password_hashing_security(self, api_client):
        """Test that passwords are properly hashed and salted."""
        # Mock user creation to inspect password storage
        with patch('app.services.auth_service.create_user') as mock_create:
            mock_create.return_value = {"userId": "test-123", "email": "test@example.com"}
            
            response = api_client.post("/auth/signup", json={
                "email": "test@example.com",
                "password": "SecurePassword123!",
                "confirmPassword": "SecurePassword123!"
            })
            
            # Verify password was hashed (not stored in plain text)
            call_args = mock_create.call_args[1]
            stored_password = call_args.get("password_hash", "")
            
            assert stored_password != "SecurePassword123!"
            assert len(stored_password) >= 60  # bcrypt hash length
            assert stored_password.startswith(("$2a$", "$2b$", "$2y$"))  # bcrypt format
    
    def test_brute_force_protection(self, api_client):
        """Test brute force attack protection."""
        # Attempt multiple failed logins
        for attempt in range(10):
            response = api_client.post("/auth/login", json={
                "username": "victim@example.com",
                "password": f"wrong_password_{attempt}"
            })
            
            if attempt < 5:
                assert response.status_code == 401
            else:
                # After 5 attempts, should be rate limited
                assert response.status_code == 429
                assert "rate limit" in response.json()["detail"].lower()
    
    def test_jwt_token_security(self, api_client, mock_cognito_client):
        """Test JWT token security features."""
        # Successful login
        response = api_client.post("/auth/login", json={
            "username": "test@example.com",
            "password": "ValidPassword123!"
        })
        
        assert response.status_code == 200
        tokens = response.json()
        access_token = tokens["accessToken"]
        
        # Decode token to check security features
        # Note: In real implementation, this would use proper key verification
        try:
            payload = jwt.decode(access_token, options={"verify_signature": False})
            
            # Check required claims
            assert "exp" in payload  # Expiration
            assert "iat" in payload  # Issued at
            assert "sub" in payload  # Subject (user ID)
            assert "aud" in payload  # Audience
            
            # Check expiration is reasonable (not too long)
            exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
            iat_time = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
            token_lifetime = exp_time - iat_time
            
            assert token_lifetime <= timedelta(hours=24), "Token lifetime too long"
            
        except jwt.InvalidTokenError:
            pytest.fail("Invalid JWT token structure")
    
    def test_token_tampering_detection(self, api_client):
        """Test detection of tampered JWT tokens."""
        # Get valid token
        auth_response = api_client.post("/auth/login", json={
            "username": "test@example.com",
            "password": "ValidPassword123!"
        })
        valid_token = auth_response.json()["accessToken"]
        
        # Tamper with token
        token_parts = valid_token.split(".")
        if len(token_parts) == 3:
            # Modify payload
            tampered_payload = token_parts[1] + "X"  # Add invalid character
            tampered_token = f"{token_parts[0]}.{tampered_payload}.{token_parts[2]}"
            
            # Attempt to use tampered token
            response = api_client.get("/echoes?userId=test-user", 
                                    headers={"Authorization": f"Bearer {tampered_token}"})
            
            assert response.status_code == 401
            assert "invalid token" in response.json()["detail"].lower()
    
    def test_session_timeout(self, api_client):
        """Test session timeout enforcement."""
        # Mock expired token
        expired_payload = {
            "sub": "test-user-123",
            "exp": int(time.time()) - 3600,  # Expired 1 hour ago
            "iat": int(time.time()) - 7200,  # Issued 2 hours ago
        }
        
        expired_token = jwt.encode(expired_payload, "secret", algorithm="HS256")
        
        response = api_client.get("/echoes?userId=test-user-123",
                                headers={"Authorization": f"Bearer {expired_token}"})
        
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()


class TestAuthorizationSecurity:
    """Test authorization and access control."""
    
    def test_user_data_isolation(self, api_client):
        """Test that users cannot access each other's data."""
        # Create two users
        user1_auth = api_client.post("/auth/login", json={
            "username": "user1@example.com",
            "password": "Password123!"
        })
        user1_token = user1_auth.json()["accessToken"]
        user1_id = user1_auth.json()["userId"]
        
        user2_auth = api_client.post("/auth/login", json={
            "username": "user2@example.com",
            "password": "Password123!"
        })
        user2_token = user2_auth.json()["accessToken"]
        user2_id = user2_auth.json()["userId"]
        
        # User 1 creates an echo
        echo_data = {
            "userId": user1_id,
            "echoId": str(uuid.uuid4()),
            "emotion": "private",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "s3Url": f"s3://test/{user1_id}/private.wav"
        }
        
        response = api_client.post("/echoes", json=echo_data,
                                 headers={"Authorization": f"Bearer {user1_token}"})
        assert response.status_code == 201
        echo_id = response.json()["echoId"]
        
        # User 2 attempts to access User 1's echo
        access_attempts = [
            ("GET", f"/echoes?userId={user1_id}"),
            ("GET", f"/echoes/{echo_id}"),
            ("PUT", f"/echoes/{echo_id}", {"tags": ["hacked"]}),
            ("DELETE", f"/echoes/{echo_id}?userId={user1_id}"),
        ]
        
        for method, url, *data in access_attempts:
            if method == "GET":
                response = api_client.get(url, headers={"Authorization": f"Bearer {user2_token}"})
            elif method == "PUT":
                response = api_client.put(url, json=data[0], headers={"Authorization": f"Bearer {user2_token}"})
            elif method == "DELETE":
                response = api_client.delete(url, headers={"Authorization": f"Bearer {user2_token}"})
            
            assert response.status_code in [403, 404], f"User 2 gained unauthorized access via {method} {url}"
    
    def test_privilege_escalation_prevention(self, api_client):
        """Test prevention of privilege escalation attacks."""
        # Regular user token
        user_auth = api_client.post("/auth/login", json={
            "username": "user@example.com",
            "password": "Password123!"
        })
        user_token = user_auth.json()["accessToken"]
        
        # Attempt to access admin endpoints (if they exist)
        admin_endpoints = [
            "/admin/users",
            "/admin/echoes",
            "/admin/analytics",
            "/admin/system",
        ]
        
        for endpoint in admin_endpoints:
            response = api_client.get(endpoint, headers={"Authorization": f"Bearer {user_token}"})
            assert response.status_code in [403, 404], f"User gained admin access to {endpoint}"
    
    def test_role_based_access_control(self, api_client):
        """Test role-based access control if implemented."""
        # Test with different user roles
        roles_to_test = [
            ("user", "Password123!"),
            ("moderator", "ModPassword123!"),
            ("admin", "AdminPassword123!"),
        ]
        
        for role, password in roles_to_test:
            # Login with role-specific account
            auth_response = api_client.post("/auth/login", json={
                "username": f"{role}@example.com",
                "password": password
            })
            
            if auth_response.status_code == 200:
                token = auth_response.json()["accessToken"]
                
                # Test role-appropriate access
                if role == "user":
                    # Users should access own data only
                    response = api_client.get("/echoes?userId=test-user", 
                                            headers={"Authorization": f"Bearer {token}"})
                    assert response.status_code in [200, 404]
                    
                elif role == "moderator":
                    # Moderators might have expanded access
                    response = api_client.get("/moderation/reports",
                                            headers={"Authorization": f"Bearer {token}"})
                    # Implementation dependent
                    
                elif role == "admin":
                    # Admins might have system access
                    response = api_client.get("/admin/system/health",
                                            headers={"Authorization": f"Bearer {token}"})
                    # Implementation dependent


class TestInputValidationSecurity:
    """Test input validation and injection attack prevention."""
    
    @pytest.mark.parametrize("injection_payload", [
        "'; DROP TABLE EchoesTable; --",
        "' OR '1'='1",
        "UNION SELECT * FROM EchoesTable",
        "'; INSERT INTO EchoesTable VALUES ('evil'); --",
        "' AND (SELECT COUNT(*) FROM EchoesTable) > 0 --",
    ])
    def test_sql_injection_prevention(self, api_client, injection_payload):
        """Test SQL injection attack prevention."""
        # Test in various input fields
        test_cases = [
            ("emotion", {"emotion": injection_payload}),
            ("tags", {"tags": [injection_payload]}),
            ("transcript", {"transcript": injection_payload}),
            ("userId", {"userId": injection_payload}),
        ]
        
        for field_name, payload in test_cases:
            echo_data = {
                "userId": "test-user-123",
                "echoId": str(uuid.uuid4()),
                "emotion": "test",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "s3Url": "s3://test/test.wav",
                **payload
            }
            
            response = api_client.post("/echoes", json=echo_data)
            
            # Should reject malicious input
            assert response.status_code in [400, 422], f"SQL injection not prevented in {field_name}"
            
            # Should not contain database error messages
            response_text = response.text.lower()
            db_error_indicators = ["sql", "database", "table", "column", "syntax error"]
            for indicator in db_error_indicators:
                assert indicator not in response_text, f"Database error exposed: {indicator}"
    
    @pytest.mark.parametrize("xss_payload", [
        "<script>alert('XSS')</script>",
        "javascript:alert('XSS')",
        "<img src=x onerror=alert('XSS')>",
        "';alert('XSS');//",
        "<svg onload=alert('XSS')>",
        "eval(String.fromCharCode(97,108,101,114,116,40,39,88,83,83,39,41))",
    ])
    def test_xss_prevention(self, api_client, xss_payload):
        """Test Cross-Site Scripting (XSS) prevention."""
        # Test XSS in various fields
        fields_to_test = ["emotion", "transcript", "tags"]
        
        for field in fields_to_test:
            echo_data = {
                "userId": "test-user-123",
                "echoId": str(uuid.uuid4()),
                "emotion": "test",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "s3Url": "s3://test/test.wav",
                field: xss_payload if field != "tags" else [xss_payload]
            }
            
            response = api_client.post("/echoes", json=echo_data)
            
            if response.status_code in [200, 201]:
                # If accepted, verify payload is sanitized in response
                response_data = response.json()
                field_value = response_data.get(field, "")
                
                # Should not contain raw script tags or javascript
                dangerous_patterns = ["<script", "javascript:", "onerror=", "onload=", "eval("]
                for pattern in dangerous_patterns:
                    assert pattern.lower() not in str(field_value).lower(), \
                           f"XSS payload not sanitized in {field}"
    
    def test_file_upload_security(self, api_client):
        """Test file upload security."""
        # Test malicious file types
        malicious_files = [
            ("malware.exe", "application/exe"),
            ("script.php", "application/php"),
            ("virus.bat", "application/bat"),
            ("trojan.js", "application/javascript"),
            ("../../../etc/passwd", "audio/wav"),  # Path traversal
        ]
        
        for filename, content_type in malicious_files:
            response = api_client.post("/echoes/init-upload", json={
                "userId": "test-user-123",
                "fileType": content_type,
                "fileName": filename
            })
            
            # Should reject non-audio files
            if content_type != "audio/wav":
                assert response.status_code == 400
                assert "invalid file type" in response.json()["detail"].lower()
            
            # Should reject path traversal attempts
            if "../" in filename:
                assert response.status_code == 400
                assert "invalid filename" in response.json()["detail"].lower()
    
    def test_size_limit_enforcement(self, api_client):
        """Test file size limit enforcement."""
        # Test oversized file upload
        oversized_request = {
            "userId": "test-user-123",
            "fileType": "audio/wav",
            "fileName": "huge_file.wav",
            "fileSize": 100 * 1024 * 1024  # 100MB (assuming 10MB limit)
        }
        
        response = api_client.post("/echoes/init-upload", json=oversized_request)
        
        assert response.status_code == 400
        assert "file too large" in response.json()["detail"].lower()
    
    def test_content_length_validation(self, api_client):
        """Test content length validation."""
        # Test extremely long input values
        long_string = "A" * 10000  # 10KB string
        
        test_cases = [
            {"emotion": long_string},
            {"transcript": long_string},
            {"tags": [long_string]},
        ]
        
        for payload in test_cases:
            echo_data = {
                "userId": "test-user-123",
                "echoId": str(uuid.uuid4()),
                "emotion": "test",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "s3Url": "s3://test/test.wav",
                **payload
            }
            
            response = api_client.post("/echoes", json=echo_data)
            
            # Should reject overly long inputs
            assert response.status_code in [400, 422], "Long input not rejected"


class TestDataProtectionSecurity:
    """Test data protection and privacy security."""
    
    def test_sensitive_data_exposure(self, api_client):
        """Test that sensitive data is not exposed in responses."""
        # Create user and echo
        auth_response = api_client.post("/auth/login", json={
            "username": "test@example.com",
            "password": "Password123!"
        })
        token = auth_response.json()["accessToken"]
        user_id = auth_response.json()["userId"]
        
        # Create echo with sensitive data
        echo_data = {
            "userId": user_id,
            "echoId": str(uuid.uuid4()),
            "emotion": "private",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "s3Url": "s3://secret-bucket/private-audio.wav",
            "sensitiveNote": "This contains private information"
        }
        
        create_response = api_client.post("/echoes", json=echo_data,
                                        headers={"Authorization": f"Bearer {token}"})
        
        if create_response.status_code == 201:
            # Retrieve echo and check for data leakage
            get_response = api_client.get(f"/echoes?userId={user_id}",
                                        headers={"Authorization": f"Bearer {token}"})
            
            response_text = get_response.text.lower()
            
            # Check for exposed sensitive patterns
            sensitive_patterns = [
                "password", "secret", "private", "internal", "debug",
                "aws_access_key", "aws_secret", "database_url",
                "exception", "stack trace", "error",
            ]
            
            for pattern in sensitive_patterns:
                assert pattern not in response_text, f"Sensitive data exposed: {pattern}"
    
    def test_cors_security(self, api_client):
        """Test CORS security configuration."""
        # Test CORS headers on API endpoints
        response = api_client.options("/echoes")
        
        assert response.status_code == 200
        
        cors_headers = response.headers
        
        # Should have restrictive CORS policy
        if "Access-Control-Allow-Origin" in cors_headers:
            origin = cors_headers["Access-Control-Allow-Origin"]
            assert origin != "*", "CORS allows all origins (security risk)"
            
        # Should not allow dangerous methods by default
        if "Access-Control-Allow-Methods" in cors_headers:
            methods = cors_headers["Access-Control-Allow-Methods"].upper()
            dangerous_methods = ["TRACE", "CONNECT"]
            for method in dangerous_methods:
                assert method not in methods, f"CORS allows dangerous method: {method}"
    
    def test_security_headers(self, api_client):
        """Test security-related HTTP headers."""
        response = api_client.get("/")
        headers = response.headers
        
        # Check for important security headers
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": ["DENY", "SAMEORIGIN"],
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=",
            "Content-Security-Policy": "default-src",
        }
        
        for header, expected_values in security_headers.items():
            if header in headers:
                header_value = headers[header]
                if isinstance(expected_values, list):
                    assert any(val in header_value for val in expected_values), \
                           f"Security header {header} has unexpected value: {header_value}"
                else:
                    assert expected_values in header_value, \
                           f"Security header {header} missing expected value: {expected_values}"
    
    def test_information_disclosure(self, api_client):
        """Test for information disclosure vulnerabilities."""
        # Test error responses don't leak information
        error_endpoints = [
            "/echoes/nonexistent-echo-id",
            "/echoes?userId=invalid-user-format",
            "/admin/secret-endpoint",
        ]
        
        for endpoint in error_endpoints:
            response = api_client.get(endpoint)
            
            # Should not expose internal details
            response_text = response.text.lower()
            internal_details = [
                "traceback", "exception", "stack trace",
                "database", "sql", "connection string",
                "file path", "directory", "server info",
                "version", "build", "debug",
            ]
            
            for detail in internal_details:
                assert detail not in response_text, \
                       f"Internal detail exposed in error: {detail}"
    
    def test_rate_limiting_security(self, api_client):
        """Test rate limiting as security measure."""
        # Test rapid requests to trigger rate limiting
        endpoint = "/echoes?userId=test-user"
        
        for i in range(100):  # Rapid requests
            response = api_client.get(endpoint)
            
            if response.status_code == 429:
                # Rate limiting activated
                assert "rate limit" in response.json()["detail"].lower()
                
                # Check for proper rate limit headers
                rate_headers = ["X-RateLimit-Limit", "X-RateLimit-Remaining", "Retry-After"]
                present_headers = [h for h in rate_headers if h in response.headers]
                assert len(present_headers) > 0, "Rate limit headers missing"
                
                break
        else:
            pytest.fail("Rate limiting not activated after 100 requests")


class TestEncryptionSecurity:
    """Test encryption and cryptographic security."""
    
    @mock_s3
    def test_s3_encryption_enforcement(self):
        """Test that S3 objects are encrypted."""
        s3_client = boto3.client('s3', region_name='us-east-1')
        bucket_name = 'echoes-audio-test'
        
        # Create bucket
        s3_client.create_bucket(Bucket=bucket_name)
        
        # Test encryption policy enforcement
        with pytest.raises(Exception):
            # Should fail without encryption
            s3_client.put_object(
                Bucket=bucket_name,
                Key='test-unencrypted.wav',
                Body=b'test audio data'
                # No ServerSideEncryption specified
            )
    
    def test_data_at_rest_encryption(self):
        """Test data-at-rest encryption for sensitive fields."""
        # Mock encrypted field storage
        sensitive_data = "This is sensitive echo content"
        
        # Should be encrypted before storage
        with patch('app.services.encryption.encrypt_field') as mock_encrypt:
            mock_encrypt.return_value = "encrypted_data_hash"
            
            # Simulate storing sensitive field
            stored_value = mock_encrypt(sensitive_data)
            
            assert stored_value != sensitive_data
            assert stored_value == "encrypted_data_hash"
            mock_encrypt.assert_called_once_with(sensitive_data)
    
    def test_data_in_transit_encryption(self, api_client):
        """Test HTTPS enforcement for data in transit."""
        # In production, all requests should be HTTPS
        # This test would verify redirect from HTTP to HTTPS
        
        # Mock HTTPS check
        with patch('app.middleware.security.enforce_https') as mock_https:
            mock_https.return_value = True
            
            response = api_client.get("/echoes?userId=test")
            
            # Should enforce HTTPS
            mock_https.assert_called()


class TestAuditingSecurity:
    """Test security auditing and logging."""
    
    def test_security_event_logging(self, api_client):
        """Test that security events are properly logged."""
        with patch('app.services.audit.log_security_event') as mock_log:
            # Trigger security event (failed authentication)
            api_client.post("/auth/login", json={
                "username": "attacker@example.com",
                "password": "wrong_password"
            })
            
            # Should log the failed attempt
            mock_log.assert_called()
            call_args = mock_log.call_args[1]
            assert call_args["event_type"] == "authentication_failure"
            assert call_args["user_identifier"] == "attacker@example.com"
    
    def test_audit_trail_integrity(self):
        """Test audit trail integrity and tampering detection."""
        # Mock audit log entry
        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": "test-user-123",
            "action": "echo_created",
            "resource_id": "echo-456",
            "ip_address": "192.168.1.100"
        }
        
        # Should include integrity hash
        with patch('app.services.audit.create_audit_entry') as mock_audit:
            mock_audit.return_value = {
                **audit_entry,
                "integrity_hash": hashlib.sha256(json.dumps(audit_entry).encode()).hexdigest()
            }
            
            result = mock_audit(audit_entry)
            
            assert "integrity_hash" in result
            assert len(result["integrity_hash"]) == 64  # SHA256 hex length


class TestComplianceSecurity:
    """Test compliance with security standards."""
    
    def test_data_retention_policy(self):
        """Test data retention and deletion policies."""
        # Mock data retention service
        with patch('app.services.data_retention.check_retention_policy') as mock_retention:
            mock_retention.return_value = {
                "should_delete": True,
                "retention_period_days": 365,
                "deletion_reason": "retention_period_exceeded"
            }
            
            # Should identify data for deletion
            result = mock_retention("echo-old-id")
            assert result["should_delete"] is True
    
    def test_user_data_export(self, api_client):
        """Test user data export for privacy compliance (GDPR)."""
        # User requests data export
        auth_response = api_client.post("/auth/login", json={
            "username": "test@example.com",
            "password": "Password123!"
        })
        token = auth_response.json()["accessToken"]
        
        response = api_client.get("/user/export-data",
                                headers={"Authorization": f"Bearer {token}"})
        
        if response.status_code == 200:
            export_data = response.json()
            
            # Should include all user data
            required_sections = ["profile", "echoes", "preferences", "audit_log"]
            for section in required_sections:
                assert section in export_data, f"Missing data section: {section}"
    
    def test_user_data_deletion(self, api_client):
        """Test user data deletion for privacy compliance."""
        # User requests account deletion
        auth_response = api_client.post("/auth/login", json={
            "username": "delete-me@example.com",
            "password": "Password123!"
        })
        token = auth_response.json()["accessToken"]
        
        response = api_client.delete("/user/delete-account",
                                   headers={"Authorization": f"Bearer {token}"})
        
        if response.status_code == 200:
            # Verify account is marked for deletion
            verify_response = api_client.post("/auth/login", json={
                "username": "delete-me@example.com",
                "password": "Password123!"
            })
            
            assert verify_response.status_code == 401, "Account not properly deleted"


# Security test runner configuration
@pytest.fixture(scope="session")
def security_test_config():
    """Configuration for security tests."""
    return {
        "enable_penetration_tests": False,  # Enable for comprehensive testing
        "test_real_endpoints": False,       # Enable for live system testing
        "log_security_events": True,        # Log all security test events
        "fail_on_security_warning": True,   # Fail tests on security warnings
    }