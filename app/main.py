"""
Vyloc API - AI-Powered Product Localization Platform

Main FastAPI application entry point.
"""

# Load environment variables FIRST, before any other imports
import os
from pathlib import Path
from dotenv import load_dotenv

# Find and load .env file from backend directory
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import get_settings
from app.routers import localization, batch, payments, websocket
from app.services.gemini_service import get_gemini_service
from app.services.storage_service import get_storage_service
from app.services.batch_service import get_batch_service
from app.schemas.localization import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    settings = get_settings()
    print(f"🚀 Starting Vyloc API v{settings.app_version}")
    print(f"📍 Environment: {settings.env}")
    
    # Initialize services
    gemini_service = get_gemini_service()
    storage_service = get_storage_service()
    batch_service = get_batch_service()
    
    if gemini_service.is_available:
        print("✅ Gemini AI service initialized")
    else:
        print("⚠️  Gemini AI service not available - check GOOGLE_API_KEY")
    
    if storage_service.is_available:
        print("✅ Google Cloud Storage initialized")
    else:
        print("⚠️  GCS not available - images will not be persisted")
    
    if batch_service.is_available:
        print("✅ Batch processing service initialized")
    else:
        print("⚠️  Batch service not available")
    
    yield
    
    # Shutdown
    print("👋 Shutting down Vyloc API")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title=settings.app_name,
        description="""
## Vyloc - AI-Powered Product Localization Platform

Vyloc enables businesses to seamlessly adapt their product ad images for global markets.
Powered by **Gemini 3 Pro Image** for state-of-the-art image generation.

### Features
- **Parallel Processing**: Localize images to multiple languages simultaneously
- **Cultural Adaptation**: Adapt visual elements to match target market demographics
- **Smart Text Translation**: AI-powered translation that preserves design integrity
- **High Resolution Output**: Support for 1K, 2K, and 4K image resolution
- **Flexible Aspect Ratios**: 1:1, 9:16, 16:9, 3:4, 4:3, and more
- **Batch Processing**: Cost-effective batch API for high-volume processing (50% lower cost)
- **Watermark Removal**: Automatic removal of AI-generated watermarks

### API Flow
1. Upload your product ad image
2. Specify target languages, markets, and output settings
3. Receive localized versions for all markets in parallel

### Endpoints
- **POST /api/v1/localize**: Real-time localization (single image, multiple languages)
- **POST /batch/jobs**: Batch processing for high-volume jobs (24-hour turnaround)
        """,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins in development
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(localization.router)
    app.include_router(batch.router)
    app.include_router(payments.router)
    app.include_router(websocket.router)
    
    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint with API information."""
        return {
            "message": f"Welcome to {settings.app_name}",
            "version": settings.app_version,
            "docs": "/docs",
            "redoc": "/redoc",
        }
    
    # Health check endpoint
    @app.get("/health", response_model=HealthResponse, tags=["Health"])
    async def health_check():
        """Health check endpoint for monitoring."""
        gemini_service = get_gemini_service()
        storage_service = get_storage_service()
        batch_service = get_batch_service()
        
        return HealthResponse(
            status="ok",
            message="Vyloc API is running",
            version=settings.app_version,
            gemini_available=gemini_service.is_available,
            gcs_available=storage_service.is_available,
            batch_available=batch_service.is_available,
        )
    
    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
