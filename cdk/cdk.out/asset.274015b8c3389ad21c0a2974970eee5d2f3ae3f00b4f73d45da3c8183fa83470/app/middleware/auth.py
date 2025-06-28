"""
Authentication middleware for Echoes API
"""
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging
import time
from typing import Callable
import uuid

from app.core.config import settings

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication and request tracking middleware
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.excluded_paths = {
            "/",
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json"
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request through authentication middleware
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/endpoint in chain
            
        Returns:
            Response from downstream or error response
        """
        # Generate request ID for tracing
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        
        # Track request timing
        start_time = time.time()
        
        # Log incoming request
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} - "
            f"Client: {request.client.host if request.client else 'unknown'}"
        )
        
        try:
            # Skip auth for excluded paths
            if request.url.path in self.excluded_paths:
                response = await call_next(request)
            else:
                # For protected endpoints, authentication is handled in dependencies
                # This middleware just adds request tracking and CORS headers
                response = await call_next(request)
            
            # Calculate request duration
            duration = time.time() - start_time
            
            # Log response
            logger.info(
                f"[{request_id}] {response.status_code} - "
                f"Duration: {duration:.3f}s"
            )
            
            # Add custom headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-API-Version"] = "1.0.0"
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"[{request_id}] Middleware error: {e} - "
                f"Duration: {duration:.3f}s"
            )
            
            # Return generic error response
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_server_error",
                    "message": "An internal server error occurred",
                    "request_id": request_id
                },
                headers={
                    "X-Request-ID": request_id,
                    "X-API-Version": "1.0.0"
                }
            )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory rate limiting middleware
    Note: In production, use Redis or similar distributed cache
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.request_counts = {}  # In-memory storage (not production ready)
        self.window_start = time.time()
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Apply rate limiting to requests
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/endpoint in chain
            
        Returns:
            Response or rate limit error
        """
        # Skip rate limiting in debug mode
        if settings.DEBUG:
            return await call_next(request)
        
        # Get client identifier
        client_ip = request.client.host if request.client else "unknown"
        
        # Get auth header for user-based limiting
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            # Use token as identifier for authenticated requests
            client_id = f"token:{auth_header[7:20]}..."  # Partial token for logging
        else:
            # Use IP for unauthenticated requests
            client_id = f"ip:{client_ip}"
        
        current_time = time.time()
        
        # Reset window if needed
        if current_time - self.window_start > settings.RATE_LIMIT_WINDOW:
            self.request_counts.clear()
            self.window_start = current_time
        
        # Check current request count
        current_count = self.request_counts.get(client_id, 0)
        
        if current_count >= settings.RATE_LIMIT_REQUESTS:
            logger.warning(f"Rate limit exceeded for {client_id}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": f"Rate limit exceeded. Max {settings.RATE_LIMIT_REQUESTS} requests per {settings.RATE_LIMIT_WINDOW} seconds.",
                    "retry_after": settings.RATE_LIMIT_WINDOW - (current_time - self.window_start)
                },
                headers={
                    "Retry-After": str(int(settings.RATE_LIMIT_WINDOW - (current_time - self.window_start))),
                    "X-RateLimit-Limit": str(settings.RATE_LIMIT_REQUESTS),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(self.window_start + settings.RATE_LIMIT_WINDOW))
                }
            )
        
        # Increment counter
        self.request_counts[client_id] = current_count + 1
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        remaining = max(0, settings.RATE_LIMIT_REQUESTS - self.request_counts[client_id])
        response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_REQUESTS)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(self.window_start + settings.RATE_LIMIT_WINDOW))
        
        return response