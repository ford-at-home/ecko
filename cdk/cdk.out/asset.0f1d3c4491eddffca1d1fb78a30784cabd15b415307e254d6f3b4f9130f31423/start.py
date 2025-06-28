#!/usr/bin/env python3
"""
Echoes API startup script
"""
import uvicorn
import sys
import os
from pathlib import Path

# Add the app directory to Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

if __name__ == "__main__":
    # Load environment variables
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)
    
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    log_level = os.getenv("LOG_LEVEL", "info").lower()
    
    print(f"Starting Echoes API on {host}:{port}")
    print(f"Debug mode: {debug}")
    print(f"Log level: {log_level}")
    
    # Start the server
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=debug,
        log_level=log_level,
        access_log=debug
    )