"""
Logging configuration for Echoes API
"""
import logging
import logging.config
import sys
from typing import Dict, Any

from app.core.config import settings


def setup_logging():
    """Setup logging configuration"""
    
    logging_config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "detailed": {
                "format": "{asctime} - {name} - {levelname} - {message}",
                "style": "{",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "simple": {
                "format": "{levelname} - {message}",
                "style": "{"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": sys.stdout,
                "formatter": "detailed" if settings.DEBUG else "simple",
                "level": settings.LOG_LEVEL
            }
        },
        "loggers": {
            "": {  # root logger
                "handlers": ["console"],
                "level": settings.LOG_LEVEL,
                "propagate": False
            },
            "app": {
                "handlers": ["console"],
                "level": settings.LOG_LEVEL,
                "propagate": False
            },
            "uvicorn": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False
            },
            "uvicorn.access": {
                "handlers": ["console"],
                "level": "WARNING" if not settings.DEBUG else "INFO",
                "propagate": False
            },
            "boto3": {
                "handlers": ["console"],
                "level": "WARNING",
                "propagate": False
            },
            "botocore": {
                "handlers": ["console"],
                "level": "WARNING", 
                "propagate": False
            }
        }
    }
    
    logging.config.dictConfig(logging_config)