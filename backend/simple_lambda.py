import json

def handler(event, context):
    """Simple handler for API Gateway"""
    
    path = event.get('path', '')
    
    # Root path - API info
    if path == '/':
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'name': 'Echoes API',
                'version': '1.0.0',
                'description': 'A soulful audio time machine - capture moments as ambient sounds tied to emotion',
                'endpoints': {
                    'health': 'GET /health - Health check (no auth)',
                    'echoes': {
                        'init_upload': 'POST /echoes/init-upload - Get S3 presigned URL (auth required)',
                        'create': 'POST /echoes - Create echo metadata (auth required)',
                        'list': 'GET /echoes - List user echoes (auth required)',
                        'random': 'GET /echoes/random - Get random echo by emotion (auth required)',
                        'get': 'GET /echoes/{id} - Get specific echo (auth required)',
                        'delete': 'DELETE /echoes/{id} - Delete echo (auth required)'
                    }
                },
                'authentication': 'AWS Cognito JWT token required for /echoes/* endpoints',
                'documentation': 'https://github.com/yourusername/echoes'
            })
        }
    
    # Health check
    elif path == '/health':
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'healthy',
                'message': 'Echoes API is running',
                'environment': 'dev'
            })
        }
    
    # Mock implementation for echo endpoints (temporary for testing)
    if path == '/echoes/init-upload' and event.get('httpMethod') == 'POST':
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'uploadUrl': 'https://echoes-audio-dev-418272766513.s3.amazonaws.com/test-audio.webm?mock-presigned-url',
                'echoId': 'echo-' + str(int(context.request_id[-8:], 16) % 1000000),
                's3_key': 'test-audio.webm',
                'fields': {}
            })
        }
    
    elif path == '/echoes' and event.get('httpMethod') == 'POST':
        body = json.loads(event.get('body', '{}'))
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'echoId': body.get('echoId', 'echo-123'),
                'userId': 'demo-user',
                's3Url': body.get('s3_key', ''),
                'emotion': body.get('emotion', 'Joy'),
                'timestamp': '2025-06-29T08:00:00Z',
                'location': body.get('location'),
                'tags': body.get('tags', []),
                'transcript': body.get('transcript', ''),
                'duration': 15
            })
        }
    
    elif path == '/echoes' and event.get('httpMethod') == 'GET':
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps([])  # Return empty list for now
        }
    
    # Default response for unhandled paths
    return {
        'statusCode': 404,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'message': 'Endpoint not found'
        })
    }