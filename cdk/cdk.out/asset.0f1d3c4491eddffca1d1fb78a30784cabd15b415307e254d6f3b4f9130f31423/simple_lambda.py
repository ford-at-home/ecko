import json

def handler(event, context):
    """Simple health check handler for testing"""
    
    path = event.get('path', '')
    
    if path == '/health':
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
            'message': 'Missing Authentication Token'
        })
    }