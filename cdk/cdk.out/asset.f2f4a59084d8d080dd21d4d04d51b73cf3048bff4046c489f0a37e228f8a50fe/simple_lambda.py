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
    
    # For all other paths, return authentication required
    return {
        'statusCode': 403,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'message': 'Authentication required. Please include a valid JWT token in the Authorization header.'
        })
    }