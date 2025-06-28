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
from app.routers import echoes
from app.middleware.auth import AuthMiddleware
from app.middleware.error_handler import ErrorHandlerMiddleware

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
    description="A soulful audio time machine that captures moments as ambient sounds tied to emotion",
    version="1.0.0",
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

# Add custom middleware
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(AuthMiddleware)

# Include routers
app.include_router(echoes.router, prefix="/api/v1", tags=["echoes"])


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Echoes API is running", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """Detailed health check endpoint"""
    return {
        "status": "healthy",
        "service": "echoes-api",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )