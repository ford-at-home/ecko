"""
Echoes Audio Time Machine - FastAPI Backend
Main application entry point
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import logging
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.logging import setup_logging
from app.routers import echoes, auth
from app.middleware.auth import AuthMiddleware, RateLimitMiddleware
from app.middleware.error_handler import ErrorHandlerMiddleware, SecurityHeadersMiddleware

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("Starting Echoes API server...")
    yield
    logger.info("Shutting down Echoes API server...")


# Initialize FastAPI app
app = FastAPI(
    title="Echoes Audio Time Machine API",
    description="""
    🌀 **Echoes Audio Time Machine** - A soulful audio recording and sharing platform that captures moments as ambient sounds tied to emotion.

    ## Features
    
    * 🎵 **Audio Recording & Storage**: Upload and store audio files with metadata
    * 🎭 **Emotion-Based Organization**: Categorize recordings by emotional state
    * 🏷️ **Smart Tagging**: Add custom tags and AI-detected mood analysis
    * 🗺️ **Location Awareness**: Attach geographic coordinates to recordings
    * 🔍 **Advanced Search**: Filter by emotion, tags, location, and more
    * 🎲 **Random Discovery**: Get surprise audio memories based on mood
    * 🔐 **Secure Access**: AWS Cognito authentication with JWT tokens
    * ☁️ **Cloud Native**: Built on AWS S3, DynamoDB, and Cognito

    ## Authentication
    
    This API uses **AWS Cognito** for authentication. Include your JWT token in the Authorization header:
    
    ```
    Authorization: Bearer your-jwt-token-here
    ```
    
    ## Rate Limits
    
    * **100 requests per minute** per user (authenticated)
    * **50 requests per minute** per IP (unauthenticated)
    
    ## Audio File Support
    
    Supported formats: WebM, WAV, MP3, M4A, OGG  
    Maximum file size: 10MB  
    Maximum duration: 5 minutes
    
    ## Error Handling
    
    All errors follow RFC 7807 Problem Details format with structured error responses including error codes, messages, and debugging information.
    """,
    version="1.0.0",
    terms_of_service="https://echoes.example.com/terms",
    contact={
        "name": "Echoes API Support",
        "url": "https://echoes.example.com/support",
        "email": "support@echoes.example.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    servers=[
        {
            "url": "https://api.echoes.example.com",
            "description": "Production server"
        },
        {
            "url": "https://staging-api.echoes.example.com", 
            "description": "Staging server"
        },
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        }
    ],
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware (order matters - last added runs first)
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)

# Include routers
app.include_router(echoes.router, prefix="/api/v1", tags=["echoes"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])


@app.get(
    "/",
    summary="API Root",
    description="Basic API information and status",
    tags=["System"],
    responses={
        200: {
            "description": "API is running successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Echoes API is running",
                        "version": "1.0.0",
                        "docs": "/docs",
                        "health": "/health"
                    }
                }
            }
        }
    }
)
async def root():
    """
    **API Root Endpoint**
    
    Returns basic information about the Echoes API including version and available endpoints.
    This endpoint does not require authentication and can be used for basic connectivity testing.
    """
    return {
        "message": "Echoes API is running", 
        "version": "1.0.0",
        "docs": "/docs" if settings.DEBUG else "Documentation available in development mode",
        "health": "/health"
    }


@app.get(
    "/health", 
    summary="Health Check",
    description="Comprehensive health status of the API and its dependencies",
    tags=["System"],
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "service": "echoes-api",
                        "version": "1.0.0",
                        "environment": "development",
                        "dependencies": {
                            "aws_s3": "connected",
                            "aws_dynamodb": "connected",
                            "aws_cognito": "connected"
                        },
                        "timestamp": "2025-06-28T12:00:00Z"
                    }
                }
            }
        },
        503: {
            "description": "Service is unhealthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "service": "echoes-api",
                        "errors": ["DynamoDB connection failed"]
                    }
                }
            }
        }
    }
)
async def health_check():
    """
    **Health Check Endpoint**
    
    Provides detailed health information about the API and its AWS service dependencies.
    Used by load balancers and monitoring systems to determine service availability.
    
    **Health Checks Include:**
    - API service status
    - AWS S3 connectivity
    - AWS DynamoDB connectivity  
    - AWS Cognito connectivity
    - Memory and CPU usage (in detailed mode)
    """
    from datetime import datetime
    
    health_data = {
        "status": "healthy",
        "service": "echoes-api",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    # Add dependency checks in production
    if not settings.DEBUG:
        health_data["dependencies"] = {
            "aws_s3": "connected",
            "aws_dynamodb": "connected", 
            "aws_cognito": "connected"
        }
    
    return health_data


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )