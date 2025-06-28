"""
Integration tests for Echoes audio time machine workflow.
Tests complete user journeys from authentication to echo creation and retrieval.
"""
import pytest
import asyncio
import json
import tempfile
import os
from datetime import datetime, timezone
from unittest.mock import Mock, patch
import boto3
from moto import mock_dynamodb, mock_s3, mock_cognitoidp
from fastapi.testclient import TestClient
import uuid

class TestEchoWorkflowIntegration:
    """Test complete echo workflow from creation to retrieval."""
    
    @pytest.fixture(autouse=True)
    def setup_aws_services(self, mock_aws_credentials):
        """Set up AWS services for integration tests."""
        with mock_dynamodb(), mock_s3(), mock_cognitoidp():
            # Create DynamoDB table
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            self.table = dynamodb.create_table(
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
            self.table.wait_until_exists()
            
            # Create S3 bucket
            s3 = boto3.resource('s3', region_name='us-east-1')
            self.bucket = s3.create_bucket(Bucket='echoes-audio-test')
            
            # Create Cognito user pool
            cognito = boto3.client('cognito-idp', region_name='us-east-1')
            self.user_pool = cognito.create_user_pool(
                PoolName='EchoesUserPool',
                Policies={
                    'PasswordPolicy': {
                        'MinimumLength': 8,
                        'RequireUppercase': True,
                        'RequireLowercase': True,
                        'RequireNumbers': True,
                        'RequireSymbols': False
                    }
                }
            )
            
            yield
    
    @pytest.mark.asyncio
    async def test_complete_echo_creation_workflow(self, api_client):
        """Test complete workflow: auth -> upload init -> record -> save -> retrieve."""
        
        # Step 1: User authentication
        auth_response = api_client.post("/auth/login", json={
            "username": "testuser@example.com",
            "password": "TestPassword123!"
        })
        assert auth_response.status_code == 200
        auth_data = auth_response.json()
        access_token = auth_data["accessToken"]
        user_id = auth_data["userId"]
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Step 2: Initialize upload
        upload_init_response = api_client.post("/echoes/init-upload", 
            json={
                "userId": user_id,
                "fileType": "audio/wav",
                "fileName": "test-echo.wav"
            },
            headers=headers
        )
        assert upload_init_response.status_code == 200
        upload_data = upload_init_response.json()
        echo_id = upload_data["echoId"]
        upload_url = upload_data["uploadUrl"]
        
        # Step 3: Simulate audio upload to S3
        with tempfile.NamedTemporaryFile(suffix='.wav') as temp_file:
            temp_file.write(b"fake audio content")
            temp_file.flush()
            
            # Mock the S3 upload process
            s3_key = f"{user_id}/{echo_id}.wav"
            self.bucket.upload_file(temp_file.name, s3_key)
            s3_url = f"s3://echoes-audio-test/{s3_key}"
        
        # Step 4: Save echo metadata
        echo_metadata = {
            "userId": user_id,
            "echoId": echo_id,
            "emotion": "joy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "s3Url": s3_url,
            "location": {
                "lat": 37.5407,
                "lng": -77.4360
            },
            "tags": ["test", "integration"],
            "transcript": "",
            "detectedMood": ""
        }
        
        save_response = api_client.post("/echoes", json=echo_metadata, headers=headers)
        assert save_response.status_code == 201
        saved_echo = save_response.json()
        assert saved_echo["echoId"] == echo_id
        assert saved_echo["emotion"] == "joy"
        
        # Step 5: Retrieve saved echo
        get_response = api_client.get(f"/echoes?userId={user_id}", headers=headers)
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert len(get_data["echoes"]) == 1
        assert get_data["echoes"][0]["echoId"] == echo_id
        
        # Step 6: Test random echo retrieval
        random_response = api_client.get(f"/echoes/random?emotion=joy&userId={user_id}", headers=headers)
        assert random_response.status_code == 200
        random_echo = random_response.json()
        assert random_echo["echoId"] == echo_id
        assert random_echo["emotion"] == "joy"
    
    @pytest.mark.asyncio
    async def test_multiple_echoes_workflow(self, api_client):
        """Test workflow with multiple echoes and emotion filtering."""
        
        # Authenticate user
        auth_response = api_client.post("/auth/login", json={
            "username": "testuser@example.com", 
            "password": "TestPassword123!"
        })
        user_id = auth_response.json()["userId"]
        access_token = auth_response.json()["accessToken"]
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Create multiple echoes with different emotions
        emotions = ["joy", "calm", "nostalgic", "peaceful"]
        echo_ids = []
        
        for emotion in emotions:
            # Initialize upload
            upload_response = api_client.post("/echoes/init-upload",
                json={
                    "userId": user_id,
                    "fileType": "audio/wav",
                    "fileName": f"{emotion}-echo.wav"
                },
                headers=headers
            )
            echo_id = upload_response.json()["echoId"]
            echo_ids.append(echo_id)
            
            # Save echo metadata
            echo_metadata = {
                "userId": user_id,
                "echoId": echo_id,
                "emotion": emotion,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "s3Url": f"s3://echoes-audio-test/{user_id}/{echo_id}.wav",
                "location": {"lat": 37.5407, "lng": -77.4360},
                "tags": [emotion, "test"],
                "transcript": f"Test {emotion} audio",
                "detectedMood": emotion
            }
            
            save_response = api_client.post("/echoes", json=echo_metadata, headers=headers)
            assert save_response.status_code == 201
        
        # Test retrieving all echoes
        all_echoes_response = api_client.get(f"/echoes?userId={user_id}", headers=headers)
        assert all_echoes_response.status_code == 200
        all_echoes = all_echoes_response.json()["echoes"]
        assert len(all_echoes) == 4
        
        # Test emotion-specific filtering
        joy_echoes_response = api_client.get(f"/echoes?userId={user_id}&emotion=joy", headers=headers)
        assert joy_echoes_response.status_code == 200
        joy_echoes = joy_echoes_response.json()["echoes"]
        assert len(joy_echoes) == 1
        assert joy_echoes[0]["emotion"] == "joy"
        
        # Test random echo with emotion filter
        calm_random_response = api_client.get(f"/echoes/random?emotion=calm&userId={user_id}", headers=headers)
        assert calm_random_response.status_code == 200
        calm_echo = calm_random_response.json()
        assert calm_echo["emotion"] == "calm"
    
    @pytest.mark.asyncio
    async def test_echo_update_workflow(self, api_client):
        """Test updating echo metadata after creation."""
        
        # Authenticate and create echo
        auth_response = api_client.post("/auth/login", json={
            "username": "testuser@example.com",
            "password": "TestPassword123!"
        })
        user_id = auth_response.json()["userId"]
        access_token = auth_response.json()["accessToken"]
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Create initial echo
        upload_response = api_client.post("/echoes/init-upload",
            json={
                "userId": user_id,
                "fileType": "audio/wav",
                "fileName": "update-test.wav"
            },
            headers=headers
        )
        echo_id = upload_response.json()["echoId"]
        
        initial_metadata = {
            "userId": user_id,
            "echoId": echo_id,
            "emotion": "neutral",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "s3Url": f"s3://echoes-audio-test/{user_id}/{echo_id}.wav",
            "tags": ["initial"],
            "transcript": "Initial transcript"
        }
        
        api_client.post("/echoes", json=initial_metadata, headers=headers)
        
        # Update echo with AI-generated transcript and mood
        update_data = {
            "tags": ["updated", "ai-processed"],
            "transcript": "Updated transcript with AI processing",
            "detectedMood": "contemplative"
        }
        
        update_response = api_client.put(f"/echoes/{echo_id}", json=update_data, headers=headers)
        assert update_response.status_code == 200
        updated_echo = update_response.json()
        
        assert updated_echo["tags"] == ["updated", "ai-processed"]
        assert updated_echo["transcript"] == "Updated transcript with AI processing"
        assert updated_echo["detectedMood"] == "contemplative"
        assert updated_echo["emotion"] == "neutral"  # Original emotion unchanged
    
    @pytest.mark.asyncio
    async def test_echo_deletion_workflow(self, api_client):
        """Test echo deletion and cleanup."""
        
        # Authenticate and create echo
        auth_response = api_client.post("/auth/login", json={
            "username": "testuser@example.com",
            "password": "TestPassword123!"
        })
        user_id = auth_response.json()["userId"]
        access_token = auth_response.json()["accessToken"]
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Create echo
        upload_response = api_client.post("/echoes/init-upload",
            json={
                "userId": user_id,
                "fileType": "audio/wav",
                "fileName": "delete-test.wav"
            },
            headers=headers
        )
        echo_id = upload_response.json()["echoId"]
        
        echo_metadata = {
            "userId": user_id,
            "echoId": echo_id,
            "emotion": "temporary",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "s3Url": f"s3://echoes-audio-test/{user_id}/{echo_id}.wav"
        }
        
        api_client.post("/echoes", json=echo_metadata, headers=headers)
        
        # Verify echo exists
        get_response = api_client.get(f"/echoes?userId={user_id}", headers=headers)
        assert len(get_response.json()["echoes"]) == 1
        
        # Delete echo
        delete_response = api_client.delete(f"/echoes/{echo_id}?userId={user_id}", headers=headers)
        assert delete_response.status_code == 204
        
        # Verify echo is deleted
        get_after_delete = api_client.get(f"/echoes?userId={user_id}", headers=headers)
        assert len(get_after_delete.json()["echoes"]) == 0
        
        # Verify 404 for non-existent echo
        get_deleted_echo = api_client.get(f"/echoes/{echo_id}", headers=headers)
        assert get_deleted_echo.status_code == 404


class TestAuthenticationIntegration:
    """Test authentication integration with echo operations."""
    
    @pytest.mark.asyncio
    async def test_unauthorized_echo_access(self, api_client):
        """Test that echo operations require authentication."""
        
        # Test without auth header
        response = api_client.get("/echoes?userId=test-user")
        assert response.status_code == 401
        
        # Test with invalid token
        headers = {"Authorization": "Bearer invalid-token"}
        response = api_client.get("/echoes?userId=test-user", headers=headers)
        assert response.status_code == 401
        
        # Test echo creation without auth
        echo_data = {
            "userId": "test-user",
            "echoId": "test-echo",
            "emotion": "joy",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        response = api_client.post("/echoes", json=echo_data)
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_cross_user_echo_access_prevention(self, api_client):
        """Test that users cannot access each other's echoes."""
        
        # Create two users
        user1_auth = api_client.post("/auth/login", json={
            "username": "user1@example.com",
            "password": "Password123!"
        })
        user1_data = user1_auth.json()
        
        user2_auth = api_client.post("/auth/login", json={
            "username": "user2@example.com", 
            "password": "Password123!"
        })
        user2_data = user2_auth.json()
        
        # User 1 creates an echo
        user1_headers = {"Authorization": f"Bearer {user1_data['accessToken']}"}
        
        upload_response = api_client.post("/echoes/init-upload",
            json={
                "userId": user1_data["userId"],
                "fileType": "audio/wav",
                "fileName": "private-echo.wav"
            },
            headers=user1_headers
        )
        echo_id = upload_response.json()["echoId"]
        
        echo_metadata = {
            "userId": user1_data["userId"],
            "echoId": echo_id,
            "emotion": "private",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "s3Url": f"s3://echoes-audio-test/{user1_data['userId']}/{echo_id}.wav"
        }
        
        api_client.post("/echoes", json=echo_metadata, headers=user1_headers)
        
        # User 2 tries to access User 1's echoes
        user2_headers = {"Authorization": f"Bearer {user2_data['accessToken']}"}
        
        # Should not see User 1's echoes
        user2_echoes = api_client.get(f"/echoes?userId={user1_data['userId']}", headers=user2_headers)
        assert user2_echoes.status_code == 403  # Forbidden
        
        # Should not be able to delete User 1's echo
        delete_response = api_client.delete(f"/echoes/{echo_id}?userId={user1_data['userId']}", headers=user2_headers)
        assert delete_response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_token_refresh_workflow(self, api_client):
        """Test token refresh and continued access."""
        
        # Initial login
        auth_response = api_client.post("/auth/login", json={
            "username": "testuser@example.com",
            "password": "TestPassword123!"
        })
        auth_data = auth_response.json()
        refresh_token = auth_data["refreshToken"]
        
        # Use refresh token to get new access token
        refresh_response = api_client.post("/auth/refresh", json={
            "refreshToken": refresh_token
        })
        assert refresh_response.status_code == 200
        new_auth_data = refresh_response.json()
        new_access_token = new_auth_data["accessToken"]
        
        # Use new access token for echo operations
        headers = {"Authorization": f"Bearer {new_access_token}"}
        echoes_response = api_client.get(f"/echoes?userId={auth_data['userId']}", headers=headers)
        assert echoes_response.status_code == 200


class TestErrorHandlingIntegration:
    """Test error handling in complete workflows."""
    
    @pytest.mark.asyncio
    async def test_s3_upload_failure_handling(self, api_client):
        """Test handling of S3 upload failures."""
        
        # Authenticate user
        auth_response = api_client.post("/auth/login", json={
            "username": "testuser@example.com",
            "password": "TestPassword123!"
        })
        user_id = auth_response.json()["userId"]
        access_token = auth_response.json()["accessToken"]
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Mock S3 service failure
        with patch('boto3.client') as mock_boto:
            mock_s3 = Mock()
            mock_s3.generate_presigned_url.side_effect = Exception("S3 service unavailable")
            mock_boto.return_value = mock_s3
            
            upload_response = api_client.post("/echoes/init-upload",
                json={
                    "userId": user_id,
                    "fileType": "audio/wav",
                    "fileName": "test.wav"
                },
                headers=headers
            )
            
            assert upload_response.status_code == 503  # Service unavailable
            assert "upload service temporarily unavailable" in upload_response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_dynamodb_failure_handling(self, api_client):
        """Test handling of DynamoDB failures."""
        
        # Authenticate user
        auth_response = api_client.post("/auth/login", json={
            "username": "testuser@example.com",
            "password": "TestPassword123!"
        })
        user_id = auth_response.json()["userId"]
        access_token = auth_response.json()["accessToken"]
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Mock DynamoDB failure
        with patch('boto3.resource') as mock_boto:
            mock_table = Mock()
            mock_table.put_item.side_effect = Exception("DynamoDB unavailable")
            mock_dynamodb = Mock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto.return_value = mock_dynamodb
            
            echo_metadata = {
                "userId": user_id,
                "echoId": str(uuid.uuid4()),
                "emotion": "test",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "s3Url": "s3://test/test.wav"
            }
            
            save_response = api_client.post("/echoes", json=echo_metadata, headers=headers)
            
            assert save_response.status_code == 503
            assert "database service temporarily unavailable" in save_response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_partial_failure_recovery(self, api_client):
        """Test recovery from partial failures in multi-step operations."""
        
        # Authenticate user
        auth_response = api_client.post("/auth/login", json={
            "username": "testuser@example.com",
            "password": "TestPassword123!"
        })
        user_id = auth_response.json()["userId"]
        access_token = auth_response.json()["accessToken"]
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Step 1: Successful upload initialization
        upload_response = api_client.post("/echoes/init-upload",
            json={
                "userId": user_id,
                "fileType": "audio/wav",
                "fileName": "recovery-test.wav"
            },
            headers=headers
        )
        assert upload_response.status_code == 200
        echo_id = upload_response.json()["echoId"]
        
        # Step 2: Simulate metadata save failure
        with patch('boto3.resource') as mock_boto:
            mock_table = Mock()
            mock_table.put_item.side_effect = Exception("Temporary failure")
            mock_dynamodb = Mock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto.return_value = mock_dynamodb
            
            echo_metadata = {
                "userId": user_id,
                "echoId": echo_id,
                "emotion": "recovery",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "s3Url": f"s3://echoes-audio-test/{user_id}/{echo_id}.wav"
            }
            
            save_response = api_client.post("/echoes", json=echo_metadata, headers=headers)
            assert save_response.status_code == 503
        
        # Step 3: Retry after service recovery (without patch)
        retry_response = api_client.post("/echoes", json=echo_metadata, headers=headers)
        assert retry_response.status_code == 201
        
        # Verify echo was saved successfully
        get_response = api_client.get(f"/echoes?userId={user_id}", headers=headers)
        assert len(get_response.json()["echoes"]) == 1
        assert get_response.json()["echoes"][0]["echoId"] == echo_id