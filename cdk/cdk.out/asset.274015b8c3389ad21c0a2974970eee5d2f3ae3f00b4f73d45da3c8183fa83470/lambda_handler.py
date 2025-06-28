"""
AWS Lambda handler for Echoes FastAPI application
Bridges FastAPI with AWS Lambda execution environment
"""

import json
import logging
from typing import Dict, Any

from mangum import Mangum
from src.main import app

# Configure logging for Lambda
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Mangum handler to adapt FastAPI for Lambda
handler = Mangum(app, lifespan="off")

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda entry point
    
    Args:
        event: Lambda event data
        context: Lambda context object
    
    Returns:
        HTTP response formatted for API Gateway
    """
    try:
        # Log request for debugging
        logger.info(f"Processing request: {event.get('httpMethod', 'UNKNOWN')} {event.get('path', '/')}")
        
        # Handle CORS preflight requests
        if event.get('httpMethod') == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Amz-Date, X-Api-Key, X-Amz-Security-Token',
                    'Access-Control-Max-Age': '86400',
                },
                'body': ''
            }
        
        # Use Mangum to handle the request
        response = handler(event, context)
        
        # Ensure CORS headers are present
        if 'headers' not in response:
            response['headers'] = {}
        
        response['headers'].update({
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Credentials': 'true',
        })
        
        logger.info(f"Response status: {response.get('statusCode', 'UNKNOWN')}")
        return response
        
    except Exception as e:
        logger.error(f"Lambda handler error: {e}", exc_info=True)
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({
                'detail': 'Internal server error',
                'type': 'lambda_error'
            })
        }