"""
Auth Lambda handler for Echoes API
Handles authentication endpoints without external dependencies
"""
import json
import uuid
import base64
import hashlib
import os
from datetime import datetime, timezone

# Import boto3 for S3 presigned URLs
try:
    import boto3
    s3_client = boto3.client('s3')
except ImportError:
    s3_client = None

# Simple in-memory storage for demo
DEMO_USERS = {}

def handler(event, context):
    """Main Lambda handler"""
    
    path = event.get('path', '')
    method = event.get('httpMethod', '')
    
    # CORS headers
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Amz-Date, X-Api-Key, X-Amz-Security-Token',
        'Access-Control-Allow-Credentials': 'true',
    }
    
    # Handle CORS preflight
    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': headers,
            'body': ''
        }
    
    # Root endpoint
    if path == '/' and method == 'GET':
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'name': 'Echoes API',
                'version': '1.0.0',
                'status': 'running'
            })
        }
    
    # Health check
    if path == '/health' and method == 'GET':
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'status': 'healthy',
                'service': 'echoes-api',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        }
    
    # Create user endpoint
    if path == '/api/v1/auth/users/create' and method == 'POST':
        try:
            body = json.loads(event.get('body', '{}'))
            email = body.get('email')
            username = body.get('username', email.split('@')[0] if email else 'user')
            
            if not email:
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({'detail': 'Email is required'})
                }
            
            # Check if user exists
            for user in DEMO_USERS.values():
                if user['email'] == email:
                    return {
                        'statusCode': 409,
                        'headers': headers,
                        'body': json.dumps({'detail': 'User already exists'})
                    }
            
            # Create new user
            user_id = str(uuid.uuid4())
            DEMO_USERS[user_id] = {
                'user_id': user_id,
                'email': email,
                'username': username,
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            
            return {
                'statusCode': 201,
                'headers': headers,
                'body': json.dumps({
                    'user_id': user_id,
                    'email': email,
                    'username': username
                })
            }
            
        except Exception as e:
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'detail': str(e)})
            }
    
    # Login endpoint
    if path == '/api/v1/auth/login' and method == 'POST':
        try:
            body = json.loads(event.get('body', '{}'))
            email = body.get('email')
            
            if not email:
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({'detail': 'Email is required'})
                }
            
            # Find or create user
            user_data = None
            for user in DEMO_USERS.values():
                if user['email'] == email:
                    user_data = user
                    break
            
            if not user_data:
                # Auto-create user for demo
                user_id = str(uuid.uuid4())
                username = email.split('@')[0]
                user_data = {
                    'user_id': user_id,
                    'email': email,
                    'username': username,
                    'created_at': datetime.now(timezone.utc).isoformat()
                }
                DEMO_USERS[user_id] = user_data
            
            # Create simple token
            token_data = {
                'sub': user_data['user_id'],
                'email': user_data['email'],
                'exp': int(datetime.now(timezone.utc).timestamp()) + 86400
            }
            token_str = base64.b64encode(json.dumps(token_data).encode()).decode()
            sig = hashlib.sha256(token_str.encode()).hexdigest()[:16]
            access_token = f"demo.{token_str}.{sig}"
            
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({
                    'access_token': access_token,
                    'token_type': 'bearer',
                    'expires_in': 86400,
                    'user': {
                        'user_id': user_data['user_id'],
                        'email': user_data['email'],
                        'username': user_data['username']
                    }
                })
            }
            
        except Exception as e:
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'detail': str(e)})
            }
    
    # Mock echo endpoints
    if path == '/api/v1/echoes/init-upload' and method == 'POST':
        echo_id = str(uuid.uuid4())
        bucket_name = os.getenv('S3_BUCKET_NAME', 'echoes-audio-dev-418272766513')
        
        # Generate presigned URL for upload
        if s3_client:
            try:
                upload_url = s3_client.generate_presigned_url(
                    'put_object',
                    Params={
                        'Bucket': bucket_name,
                        'Key': f"{echo_id}.webm",
                        'ContentType': 'audio/webm'
                    },
                    ExpiresIn=3600  # 1 hour
                )
            except Exception as e:
                # Fallback to mock URL if presigned URL generation fails
                upload_url = f"https://{bucket_name}.s3.amazonaws.com/{echo_id}.webm?mock-presigned"
        else:
            # No boto3 available, use mock URL
            upload_url = f"https://{bucket_name}.s3.amazonaws.com/{echo_id}.webm?mock-presigned"
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'uploadUrl': upload_url,
                'echoId': echo_id
            })
        }
    
    if path == '/api/v1/echoes' and method == 'POST':
        query_params = event.get('queryStringParameters', {}) or {}
        echo_id = query_params.get('echo_id', str(uuid.uuid4()))
        
        try:
            body = json.loads(event.get('body', '{}'))
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({
                    'echoId': echo_id,
                    'userId': 'demo-user',
                    'emotion': body.get('emotion', 'joy'),
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    's3Url': f"https://echoes-audio-dev-418272766513.s3.amazonaws.com/{echo_id}.webm",
                    'duration': body.get('duration_seconds', 15),
                    'tags': body.get('tags', []),
                    'transcript': body.get('transcript', ''),
                    'location': body.get('location')
                })
            }
        except:
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'detail': 'Error processing request'})
            }
    
    if path == '/api/v1/echoes' and method == 'GET':
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps([])
        }
    
    # Default 404
    return {
        'statusCode': 404,
        'headers': headers,
        'body': json.dumps({'detail': f'Not found: {method} {path}'})
    }