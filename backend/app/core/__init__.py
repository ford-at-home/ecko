"""
Core utilities and configuration for Echoes API
"""
from .config import settings
from .logging import setup_logging

__all__ = ["settings", "setup_logging"]