"""
Error handling middleware for Echoes API
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from pydantic import ValidationError
import logging
import traceback
from typing import Callable
from datetime import datetime

from app.models.user import ErrorResponse
from app.core.config import settings

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Global error handling middleware
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> JSONResponse:
        """
        Handle all errors and format consistent error responses
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/endpoint in chain
            
        Returns:
            Response or formatted error response
        """
        try:
            response = await call_next(request)
            return response
            
        except HTTPException as e:
            # Handle FastAPI HTTP exceptions
            request_id = getattr(request.state, 'request_id', 'unknown')
            
            logger.warning(
                f"[{request_id}] HTTP Exception: {e.status_code} - {e.detail}"
            )
            
            error_response = ErrorResponse(
                error=self._get_error_type(e.status_code),
                message=str(e.detail),
                details={
                    "status_code": e.status_code,
                    "path": str(request.url.path),
                    "method": request.method,
                    "request_id": request_id
                }
            )
            
            return JSONResponse(
                status_code=e.status_code,
                content=error_response.dict(),
                headers=getattr(e, 'headers', None)
            )
            
        except ValidationError as e:
            # Handle Pydantic validation errors
            request_id = getattr(request.state, 'request_id', 'unknown')
            
            logger.warning(f"[{request_id}] Validation Error: {e}")
            
            error_response = ErrorResponse(
                error="validation_error",
                message="Request validation failed",
                details={
                    "validation_errors": e.errors(),
                    "path": str(request.url.path),
                    "method": request.method,
                    "request_id": request_id
                }
            )
            
            return JSONResponse(
                status_code=422,
                content=error_response.dict()
            )
            
        except ValueError as e:
            # Handle custom validation errors
            request_id = getattr(request.state, 'request_id', 'unknown')
            
            logger.warning(f"[{request_id}] Value Error: {e}")
            
            error_response = ErrorResponse(
                error="invalid_input",
                message=str(e),
                details={
                    "path": str(request.url.path),
                    "method": request.method,
                    "request_id": request_id
                }
            )
            
            return JSONResponse(
                status_code=400,
                content=error_response.dict()
            )
            
        except Exception as e:
            # Handle unexpected errors
            request_id = getattr(request.state, 'request_id', 'unknown')
            
            logger.error(
                f"[{request_id}] Unexpected Error: {e}\n"
                f"Traceback: {traceback.format_exc()}"
            )
            
            # Don't expose internal errors in production
            if settings.DEBUG:
                error_message = str(e)
                error_details = {
                    "exception_type": type(e).__name__,
                    "traceback": traceback.format_exc(),
                    "path": str(request.url.path),
                    "method": request.method,
                    "request_id": request_id
                }
            else:
                error_message = "An internal server error occurred"
                error_details = {
                    "path": str(request.url.path),
                    "method": request.method,
                    "request_id": request_id
                }
            
            error_response = ErrorResponse(
                error="internal_server_error",
                message=error_message,
                details=error_details
            )
            
            return JSONResponse(
                status_code=500,
                content=error_response.dict()
            )
    
    def _get_error_type(self, status_code: int) -> str:
        """
        Map HTTP status codes to error types
        
        Args:
            status_code: HTTP status code
            
        Returns:
            Error type string
        """
        error_types = {
            400: "bad_request",
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            405: "method_not_allowed",
            409: "conflict",
            422: "validation_error",
            429: "rate_limit_exceeded",
            500: "internal_server_error",
            502: "bad_gateway",
            503: "service_unavailable",
            504: "gateway_timeout"
        }
        
        return error_types.get(status_code, "unknown_error")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable):
        """
        Add security headers to response
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/endpoint in chain
            
        Returns:
            Response with security headers
        """
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Add HSTS in production
        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Content Security Policy for API
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none';"
        
        return response