"""
AWS Lambda handler for Echoes FastAPI application
Bridges FastAPI with AWS Lambda execution environment
Optimized for cold start performance and production deployment
"""

import json
import logging
import os
import sys
from typing import Dict, Any

# Add app directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from mangum import Mangum

# Configure logging for Lambda
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variables for connection reuse and cold start optimization
_app = None
_handler = None

def get_app():
    """
    Lazy-load the FastAPI app to optimize cold starts
    Reuse app instance across Lambda invocations
    """
    global _app
    if _app is None:
        try:
            logger.info("Initializing FastAPI app...")
            from app.main import app
            _app = app
            logger.info("FastAPI app initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize FastAPI app: {e}", exc_info=True)
            raise
    return _app

def get_handler():
    """
    Lazy-load the Mangum handler to optimize cold starts
    Reuse handler instance across Lambda invocations
    """
    global _handler
    if _handler is None:
        try:
            logger.info("Initializing Mangum handler...")
            app = get_app()
            _handler = Mangum(
                app, 
                lifespan="off",  # Disable lifespan for Lambda
                api_gateway_base_path="",  # Handle base path properly
                text_mime_types=[
                    "application/json",
                    "application/javascript",
                    "application/xml",
                    "application/vnd.api+json",
                ]
            )
            logger.info("Mangum handler initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Mangum handler: {e}", exc_info=True)
            raise
    return _handler

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda entry point with optimized cold start handling
    
    Args:
        event: Lambda event data from API Gateway
        context: Lambda context object
    
    Returns:
        HTTP response formatted for API Gateway
    """
    # Set Lambda context info for logging
    request_id = getattr(context, 'aws_request_id', 'unknown')
    logger.info(f"Request ID: {request_id}")
    
    try:
        # Extract request details for logging
        http_method = event.get('httpMethod', 'UNKNOWN')
        path = event.get('path', '/')
        source_ip = event.get('requestContext', {}).get('identity', {}).get('sourceIp', 'unknown')
        
        logger.info(f"Processing request: {http_method} {path} from {source_ip}")
        
        # Get CORS origins from environment
        cors_origins = os.getenv('CORS_ALLOW_ORIGINS', '*')
        cors_origin = cors_origins.split(',')[0] if cors_origins != '*' else '*'
        
        # Standard CORS headers
        cors_headers = {
            'Access-Control-Allow-Origin': cors_origin,
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Amz-Date, X-Api-Key, X-Amz-Security-Token, X-Amz-User-Agent',
            'Access-Control-Max-Age': '86400',
            'Access-Control-Allow-Credentials': 'true',
        }
        
        # Handle CORS preflight requests
        if http_method == 'OPTIONS':
            logger.info("Handling CORS preflight request")
            return {
                'statusCode': 200,
                'headers': cors_headers,
                'body': ''
            }
        
        # Get the Mangum handler (lazy-loaded)
        handler = get_handler()
        
        # Process the request through FastAPI
        logger.debug(f"Event details: {json.dumps(event, default=str)}")
        response = handler(event, context)
        
        # Ensure response has headers dict
        if 'headers' not in response:
            response['headers'] = {}
        
        # Always add CORS headers to response
        response['headers'].update(cors_headers)
        
        # Log response details
        status_code = response.get('statusCode', 'UNKNOWN')
        logger.info(f"Response status: {status_code} for {http_method} {path}")
        
        # Add Lambda metadata to response headers for debugging
        if os.getenv('DEBUG', 'false').lower() == 'true':
            response['headers'].update({
                'X-Lambda-Request-Id': request_id,
                'X-Lambda-Function-Name': context.function_name,
                'X-Lambda-Function-Version': context.function_version,
            })
        
        return response
        
    except ImportError as e:
        logger.error(f"Import error - check dependencies: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': cors_origin,
            },
            'body': json.dumps({
                'detail': 'Configuration error - dependencies not found',
                'type': 'import_error',
                'request_id': request_id
            })
        }
    except Exception as e:
        logger.error(f"Lambda handler error: {e}", exc_info=True)
        
        # Return detailed error in development, generic in production
        is_debug = os.getenv('DEBUG', 'false').lower() == 'true'
        error_detail = str(e) if is_debug else 'Internal server error'
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': cors_origin,
            },
            'body': json.dumps({
                'detail': error_detail,
                'type': 'lambda_error',
                'request_id': request_id
            })
        }

# Warm-up handler for provisioned concurrency
def warmup_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handler for Lambda warm-up events to reduce cold starts
    """
    try:
        logger.info("Warming up Lambda function...")
        
        # Pre-load the app and handler
        get_handler()
        
        logger.info("Lambda function warmed up successfully")
        return {
            'statusCode': 200,
            'body': json.dumps({'status': 'warmed'})
        }
    except Exception as e:
        logger.error(f"Warmup error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'status': 'error', 'detail': str(e)})
        }