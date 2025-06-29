"""
Minimal Lambda handler for Echoes API
Handles authentication endpoints with JWT support
"""
import json
import os
import logging
import uuid
from datetime import datetime, timedelta
import jwt

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configuration
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_MINUTES = 60 * 24  # 24 hours

# In-memory user storage (for demo purposes)
DEMO_USERS = {}

def cors_headers(origin='*'):
    """Generate CORS headers"""
    return {
        'Access-Control-Allow-Origin': origin,
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Amz-Date, X-Api-Key, X-Amz-Security-Token',
        'Access-Control-Allow-Credentials': 'true',
    }

def response(status_code, body, headers=None):
    """Generate API Gateway response"""
    resp_headers = {'Content-Type': 'application/json'}
    resp_headers.update(cors_headers())
    if headers:
        resp_headers.update(headers)
    
    return {
        'statusCode': status_code,
        'headers': resp_headers,
        'body': json.dumps(body) if isinstance(body, dict) else body
    }

def create_jwt_token(user_id, email):
    """Create a JWT token"""
    payload = {
        'sub': user_id,
        'email': email,
        'exp': datetime.utcnow() + timedelta(minutes=JWT_EXPIRATION_MINUTES),
        'iat': datetime.utcnow(),
        'type': 'access'
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def handler(event, context):
    """Main Lambda handler"""
    logger.info(f"Received event: {json.dumps(event)}")
    
    path = event.get('path', '')
    method = event.get('httpMethod', '')
    
    # Handle CORS preflight
    if method == 'OPTIONS':
        return response(200, '')
    
    # Root endpoint
    if path == '/' and method == 'GET':
        return response(200, {
            'name': 'Echoes API',
            'version': '1.0.0',
            'status': 'running'
        })
    
    # Health check
    if path == '/health' and method == 'GET':
        return response(200, {
            'status': 'healthy',
            'service': 'echoes-api',
            'timestamp': datetime.utcnow().isoformat()
        })
    
    # Create demo user endpoint
    if path == '/api/v1/auth/users/create' and method == 'POST':
        try:
            body = json.loads(event.get('body', '{}'))
            email = body.get('email')
            username = body.get('username', email.split('@')[0] if email else 'user')
            
            if not email:
                return response(400, {'detail': 'Email is required'})
            
            # Check if user exists
            for user in DEMO_USERS.values():
                if user['email'] == email:
                    return response(409, {'detail': 'User already exists'})
            
            # Create new user
            user_id = str(uuid.uuid4())
            DEMO_USERS[user_id] = {
                'user_id': user_id,
                'email': email,
                'username': username,
                'created_at': datetime.utcnow().isoformat()
            }
            
            return response(201, {
                'user_id': user_id,
                'email': email,
                'username': username
            })
            
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return response(500, {'detail': str(e)})
    
    # Login endpoint
    if path == '/api/v1/auth/login' and method == 'POST':
        try:
            body = json.loads(event.get('body', '{}'))
            email = body.get('email')
            
            if not email:
                return response(400, {'detail': 'Email is required'})
            
            # Find user by email
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
                    'created_at': datetime.utcnow().isoformat()
                }
                DEMO_USERS[user_id] = user_data
            
            # Generate token
            access_token = create_jwt_token(user_data['user_id'], user_data['email'])
            
            return response(200, {
                'access_token': access_token,
                'token_type': 'bearer',
                'expires_in': JWT_EXPIRATION_MINUTES * 60,
                'user': {
                    'user_id': user_data['user_id'],
                    'email': user_data['email'],
                    'username': user_data['username']
                }
            })
            
        except Exception as e:
            logger.error(f"Error in login: {e}")
            return response(500, {'detail': str(e)})
    
    # Mock echo endpoints for now
    if path == '/api/v1/echoes/init-upload' and method == 'POST':
        echo_id = str(uuid.uuid4())
        upload_url = f"https://echoes-audio-dev-418272766513.s3.amazonaws.com/{echo_id}.webm?mock-presigned-url"
        
        return response(200, {
            'uploadUrl': upload_url,
            'echoId': echo_id
        })
    
    if path == '/api/v1/echoes' and method == 'POST':
        return response(200, {
            'echoId': event.get('queryStringParameters', {}).get('echo_id', str(uuid.uuid4())),
            'userId': 'demo-user',
            'emotion': 'joy',
            'timestamp': datetime.utcnow().isoformat(),
            's3Url': 'https://mock-s3-url.com/audio.webm',
            'duration': 15
        })
    
    if path == '/api/v1/echoes' and method == 'GET':
        return response(200, [])
    
    # Default 404
    return response(404, {'detail': 'Not found'})