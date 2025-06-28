"""
Main FastAPI application for Echoes
Audio time machine web app
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from .api.echoes import router as echoes_router
from .services.s3_service import s3_service
from .services.dynamodb_service import dynamodb_service
from .services.auth_service import auth_service


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    Handles startup and shutdown events
    """
    # Startup
    logger.info("Starting Echoes API server...")
    
    # Perform health checks on all services
    try:
        s3_health = s3_service.health_check()
        dynamodb_health = dynamodb_service.health_check()
        auth_health = auth_service.health_check()
        
        logger.info(f"S3 service health: {s3_health['status']}")
        logger.info(f"DynamoDB service health: {dynamodb_health['status']}")
        logger.info(f"Auth service health: {auth_health['status']}")
        
        if (s3_health['status'] != 'healthy' or 
            dynamodb_health['status'] != 'healthy' or 
            auth_health['status'] != 'healthy'):
            logger.warning("Some services are not healthy - check configuration")
        
    except Exception as e:
        logger.error(f"Error during startup health checks: {e}")
    
    logger.info("Echoes API server started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Echoes API server...")


# Create FastAPI application
app = FastAPI(
    title="Echoes API",
    description="Audio time machine for capturing and resurfacing emotional moments",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add trusted host middleware for security
trusted_hosts = os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1").split(",")
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=trusted_hosts
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler for unhandled errors
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": "internal_error"
        }
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Application health check endpoint
    """
    try:
        # Check all services
        s3_health = s3_service.health_check()
        dynamodb_health = dynamodb_service.health_check()
        auth_health = auth_service.health_check()
        
        overall_status = "healthy"
        if (s3_health['status'] != 'healthy' or 
            dynamodb_health['status'] != 'healthy' or 
            auth_health['status'] != 'healthy'):
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "version": "1.0.0",
            "services": {
                "s3": s3_health,
                "dynamodb": dynamodb_health,
                "auth": auth_health
            }
        }
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@app.get("/")
async def root():
    """
    Root endpoint
    """
    return {
        "message": "Welcome to Echoes API",
        "description": "Audio time machine for capturing and resurfacing emotional moments",
        "version": "1.0.0",
        "docs": "/docs"
    }


# Include routers
app.include_router(echoes_router)


# Additional middleware for request logging
@app.middleware("http")
async def log_requests(request, call_next):
    """
    Log all HTTP requests
    """
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.4f}s"
    )
    
    return response


if __name__ == "__main__":
    import uvicorn
    import time
    
    # Run with uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("ENVIRONMENT", "development") == "development",
        log_level="info"
    )