"""
Configuration management for Echoes API
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional
from datetime import datetime
import os


class Settings(BaseSettings):
    """Application settings"""
    
    # Basic app settings
    APP_NAME: str = "Echoes API"
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=True, env="DEBUG")
    PORT: int = Field(default=8000, env="PORT")
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    
    # CORS settings
    ALLOWED_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        env="ALLOWED_ORIGINS"
    )
    
    # AWS Settings
    AWS_REGION: str = Field(default="us-east-1", env="AWS_REGION")
    AWS_ACCESS_KEY_ID: Optional[str] = Field(default=None, env="AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(default=None, env="AWS_SECRET_ACCESS_KEY")
    
    # S3 Settings
    S3_BUCKET_NAME: str = Field(default="echoes-audio-dev", env="S3_BUCKET_NAME")
    S3_PRESIGNED_URL_EXPIRATION: int = Field(default=3600, env="S3_PRESIGNED_URL_EXPIRATION")  # 1 hour
    
    # DynamoDB Settings
    DYNAMODB_TABLE_NAME: str = Field(default="EchoesTable", env="DYNAMODB_TABLE_NAME")
    DYNAMODB_ENDPOINT_URL: Optional[str] = Field(default=None, env="DYNAMODB_ENDPOINT_URL")
    
    # Cognito Settings
    COGNITO_USER_POOL_ID: Optional[str] = Field(default=None, env="COGNITO_USER_POOL_ID")
    COGNITO_CLIENT_ID: Optional[str] = Field(default=None, env="COGNITO_CLIENT_ID")
    COGNITO_REGION: str = Field(default="us-east-1", env="COGNITO_REGION")
    
    # JWT Settings
    JWT_SECRET_KEY: str = Field(default="your-secret-key-change-in-production", env="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    JWT_EXPIRATION_MINUTES: int = Field(default=60 * 24, env="JWT_EXPIRATION_MINUTES")  # 24 hours
    
    # Audio file settings
    MAX_AUDIO_FILE_SIZE: int = Field(default=10 * 1024 * 1024, env="MAX_AUDIO_FILE_SIZE")  # 10MB
    ALLOWED_AUDIO_FORMATS: List[str] = Field(
        default=["webm", "wav", "mp3", "m4a", "ogg"],
        env="ALLOWED_AUDIO_FORMATS"
    )
    
    # Rate limiting
    RATE_LIMIT_REQUESTS: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    RATE_LIMIT_WINDOW: int = Field(default=60, env="RATE_LIMIT_WINDOW")  # seconds
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        
    def get_s3_key(self, user_id: str, echo_id: str, file_extension: str) -> str:
        """Generate S3 key for audio file (legacy format)"""
        return f"{user_id}/{echo_id}.{file_extension}"
    
    def get_s3_key_with_timestamp(self, user_id: str, echo_id: str, file_extension: str, timestamp: datetime = None) -> str:
        """Generate S3 key with timestamp structure: user_id/year/month/day/echo_id.extension"""
        if not timestamp:
            timestamp = datetime.utcnow()
        
        year = timestamp.strftime('%Y')
        month = timestamp.strftime('%m')
        day = timestamp.strftime('%d')
        
        return f"{user_id}/{year}/{month}/{day}/{echo_id}.{file_extension}"
    
    def get_s3_url(self, key: str) -> str:
        """Generate S3 URL for audio file"""
        return f"s3://{self.S3_BUCKET_NAME}/{key}"


# Create settings instance
settings = Settings()