"""
Vyloc API Entry Point

This file serves as the entry point for running the API.
The actual app is defined in app/main.py with all routers included.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables FIRST, before any other imports
# Use the directory of this file to find .env
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

if __name__ == "__main__":
    import uvicorn
    from app.core.config import get_settings
    
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
