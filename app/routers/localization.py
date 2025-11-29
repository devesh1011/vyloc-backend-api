"""
Localization API Router.

Handles image upload and localization processing endpoints.
"""

import time
import logging
import base64
from datetime import datetime
from typing import Annotated, List, Optional

from fastapi import APIRouter, File, Form, UploadFile, HTTPException, Depends

from app.core.config import get_settings, Settings
from app.schemas.localization import (
    LocalizationResponse,
    LocalizedImage,
    LocalizationStatus,
    TargetLanguage,
    TargetMarket,
)
from app.services.gemini_service import get_gemini_service
from app.services.watermark_service import get_watermark_service
from app.services.storage_service import get_storage_service
from app.services.supabase_service import get_supabase_service

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


router = APIRouter(prefix="/api/v1/localize", tags=["Localization"])


def get_settings_dep() -> Settings:
    """Dependency for settings."""
    return get_settings()


@router.post(
    "/",
    response_model=LocalizationResponse,
    summary="Localize an ad image",
    description="Upload an ad image and localize it to multiple languages/markets in parallel.",
)
async def localize_image(
    file: Annotated[UploadFile, File(description="The ad image to localize")],
    target_languages: Annotated[
        str,
        Form(description="Comma-separated list of target languages (e.g., 'hindi,japanese,german')")
    ],
    target_markets: Annotated[
        Optional[str],
        Form(description="Comma-separated list of target markets (optional)")
    ] = None,
    source_language: Annotated[
        str,
        Form(description="Source language of the ad image")
    ] = "english",
    preserve_faces: Annotated[
        bool,
        Form(description="If true, preserve original faces; if false, adapt to target demographics")
    ] = False,
    image_size: Annotated[
        str,
        Form(description="Output image size: 1K, 2K, or 4K")
    ] = "1K",
    aspect_ratio: Annotated[
        Optional[str],
        Form(description="Output aspect ratio: 1:1, 9:16, 16:9, 3:4, 4:3, etc. (defaults to original)")
    ] = None,
    remove_watermark: Annotated[
        bool,
        Form(description="If true, remove AI-generated watermarks from output images")
    ] = True,
    user_id: Annotated[
        Optional[str],
        Form(description="User ID for tracking and credit deduction (optional)")
    ] = None,
    settings: Settings = Depends(get_settings_dep),
):
    """
    Localize an ad image to multiple languages and markets.
    
    This endpoint:
    1. Accepts an uploaded image
    2. Processes it in parallel for all target languages using Gemini AI
    3. Removes AI watermarks from generated images
    4. Uploads results to cloud storage
    5. Returns URLs to all localized versions
    """
    start_time = time.time()
    
    # Validate file
    if file.content_type not in settings.supported_image_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image format. Supported formats: {settings.supported_image_formats}"
        )
    
    # Parse target languages
    try:
        languages: List[TargetLanguage] = [
            TargetLanguage(lang.strip().lower())
            for lang in target_languages.split(",")
            if lang.strip()
        ]
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target language: {str(e)}"
        )
    
    if not languages:
        raise HTTPException(status_code=400, detail="At least one target language is required")
    
    if len(languages) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 languages per request")
    
    # Parse target markets (optional)
    markets: Optional[List[Optional[TargetMarket]]] = None
    if target_markets:
        try:
            markets = [
                TargetMarket(market.strip().lower()) if market.strip() else None
                for market in target_markets.split(",")
            ]
        except ValueError:
            # If market parsing fails, just use None (will be inferred)
            markets = None
    
    # Read image bytes
    image_bytes = await file.read()
    
    # Check file size
    max_size = settings.max_image_size_mb * 1024 * 1024
    if len(image_bytes) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"Image too large. Maximum size: {settings.max_image_size_mb}MB"
        )
    
    # Get services
    gemini_service = get_gemini_service()
    watermark_service = get_watermark_service()
    storage_service = get_storage_service()
    
    # Check Gemini availability
    if not gemini_service.is_available:
        raise HTTPException(
            status_code=503,
            detail="Gemini AI service is not available. Please check API configuration."
        )
    
    # Generate job ID
    job_id = storage_service.generate_job_id()
    
    # Upload original image
    original_url = ""
    if storage_service.is_available:
        url, error = await storage_service.upload_original_image(
            image_bytes=image_bytes,
            job_id=job_id,
            content_type=file.content_type or "image/png",
        )
        if url:
            original_url = url
    
    # Process localization in parallel
    localized_images = await gemini_service.localize_image_batch(
        image_bytes=image_bytes,
        target_languages=languages,
        target_markets=markets,
        source_language=source_language,
        preserve_faces=preserve_faces,
        aspect_ratio=aspect_ratio,
        image_size=image_size,
    )
    
    # Post-process: remove watermarks and upload to storage
    final_images: List[LocalizedImage] = []
    
    for img in localized_images:
        if img.status == LocalizationStatus.COMPLETED:
            # Get the image bytes stored on the object
            img_bytes = getattr(img, '_image_bytes', None)
            
            if img_bytes:
                logger.info(f"📦 Processing {img.language.value}: {len(img_bytes)} bytes")
                
                # Remove watermark if requested (uses neural network model)
                if remove_watermark:
                    cleaned_bytes, error = await watermark_service.remove_watermark(
                        img_bytes,
                    )
                    if cleaned_bytes:
                        img_bytes = cleaned_bytes
                        logger.info(f"🧹 Watermark removed for {img.language.value}")
                
                # Upload to storage
                if storage_service.is_available:
                    logger.info(f"☁️ Uploading {img.language.value} to GCS...")
                    url, error = await storage_service.upload_localized_image(
                        image_bytes=img_bytes,
                        job_id=job_id,
                        language=img.language.value,
                    )
                    if url:
                        img.image_url = url
                        logger.info(f"✅ {img.language.value} uploaded: {url}")
                    else:
                        logger.error(f"❌ Failed to upload {img.language.value}: {error}")
                else:
                    logger.warning("⚠️ Storage service not available - image_url will be empty")
                
                # Clean up the temporary bytes
                delattr(img, '_image_bytes') if hasattr(img, '_image_bytes') else None
            else:
                logger.warning(f"⚠️ No image bytes for {img.language.value}")
        
        final_images.append(img)
    
    # Calculate total processing time
    total_time_ms = int((time.time() - start_time) * 1000)
    
    # Determine overall status
    completed_count = sum(1 for img in final_images if img.status == LocalizationStatus.COMPLETED)
    failed_count = sum(1 for img in final_images if img.status == LocalizationStatus.FAILED)
    
    if failed_count == len(final_images):
        overall_status = LocalizationStatus.FAILED
    elif completed_count == len(final_images):
        overall_status = LocalizationStatus.COMPLETED
    else:
        overall_status = LocalizationStatus.COMPLETED  # Partial success
    
    # Save job to Supabase and deduct credits if user_id is provided
    if user_id and completed_count > 0:
        supabase_service = get_supabase_service()
        
        if supabase_service.is_available:
            # Prepare localized images data for storage
            localized_images_data = [
                {
                    "language": img.language.value if hasattr(img.language, 'value') else str(img.language),
                    "market": img.market.value if img.market and hasattr(img.market, 'value') else (str(img.market) if img.market else None),
                    "image_url": img.image_url,
                    "status": img.status.value if hasattr(img.status, 'value') else str(img.status),
                    "processing_time_ms": img.processing_time_ms,
                    "error_message": img.error_message,
                }
                for img in final_images
            ]
            
            # Save job to database
            success, error = await supabase_service.save_localization_job(
                job_id=job_id,
                user_id=user_id,
                original_image_url=original_url,
                localized_images=localized_images_data,
                total_processing_time_ms=total_time_ms,
                target_languages=[img.language.value for img in final_images],
            )
            
            if success:
                logger.info(f"💾 Job {job_id} saved to database")
                
                # Deduct credits
                deduct_success, deduct_error = await supabase_service.deduct_credits(
                    user_id=user_id,
                    credits_to_deduct=completed_count,
                )
                
                if deduct_success:
                    logger.info(f"💳 Deducted {completed_count} credits for user {user_id}")
                else:
                    logger.error(f"❌ Failed to deduct credits: {deduct_error}")
            else:
                logger.error(f"❌ Failed to save job: {error}")
        else:
            logger.warning("⚠️ Supabase not available - job not saved")
    
    return LocalizationResponse(
        job_id=job_id,
        status=overall_status,
        original_image_url=original_url,
        localized_images=final_images,
        total_processing_time_ms=total_time_ms,
        created_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )


@router.post(
    "/async",
    summary="Localize an ad image asynchronously",
    description="Upload an ad image and queue it for localization. Returns immediately with a job ID. Use WebSocket /ws/jobs/{job_id} for real-time updates.",
)
async def localize_image_async(
    file: Annotated[UploadFile, File(description="The ad image to localize")],
    target_languages: Annotated[
        str,
        Form(description="Comma-separated list of target languages (e.g., 'hindi,japanese,german')")
    ],
    target_markets: Annotated[
        Optional[str],
        Form(description="Comma-separated list of target markets (optional)")
    ] = None,
    source_language: Annotated[
        str,
        Form(description="Source language of the ad image")
    ] = "english",
    preserve_faces: Annotated[
        bool,
        Form(description="If true, preserve original faces; if false, adapt to target demographics")
    ] = False,
    image_size: Annotated[
        str,
        Form(description="Output image size: 1K, 2K, or 4K")
    ] = "1K",
    aspect_ratio: Annotated[
        Optional[str],
        Form(description="Output aspect ratio: 1:1, 9:16, 16:9, 3:4, 4:3, etc. (defaults to original)")
    ] = None,
    remove_watermark: Annotated[
        bool,
        Form(description="If true, remove AI-generated watermarks from output images")
    ] = True,
    user_id: Annotated[
        Optional[str],
        Form(description="User ID for tracking and credit deduction (required for async)")
    ] = None,
    settings: Settings = Depends(get_settings_dep),
):
    """
    Queue an image for async localization.
    
    This endpoint:
    1. Validates the uploaded image
    2. Queues the localization task
    3. Returns immediately with a job ID
    4. Client connects to WebSocket for real-time updates
    """
    # Validate file
    if file.content_type not in settings.supported_image_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image format. Supported formats: {settings.supported_image_formats}"
        )
    
    # Require user_id for async processing
    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="user_id is required for async processing"
        )
    
    # Parse target languages
    try:
        languages = [
            lang.strip().lower()
            for lang in target_languages.split(",")
            if lang.strip()
        ]
        # Validate languages
        for lang in languages:
            TargetLanguage(lang)  # This will raise if invalid
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target language: {str(e)}"
        )
    
    if not languages:
        raise HTTPException(status_code=400, detail="At least one target language is required")
    
    if len(languages) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 languages per request")
    
    # Check credits before processing (defense in depth - frontend also validates)
    supabase_service = get_supabase_service()
    credits_required = len(languages)
    has_credits, credits_remaining, credit_error = await supabase_service.check_credits_available(
        user_id=user_id,
        credits_required=credits_required
    )
    
    if not has_credits:
        raise HTTPException(
            status_code=402,  # Payment Required
            detail=credit_error or f"Insufficient credits. You need {credits_required} credits but only have {credits_remaining} available."
        )
    
    # Parse target markets (optional)
    markets = None
    if target_markets:
        markets = [
            market.strip().lower() if market.strip() else None
            for market in target_markets.split(",")
        ]
    
    # Read image bytes
    image_bytes = await file.read()
    
    # Check file size
    max_size = settings.max_image_size_mb * 1024 * 1024
    if len(image_bytes) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"Image too large. Maximum size: {settings.max_image_size_mb}MB"
        )
    
    # Generate job ID
    storage_service = get_storage_service()
    job_id = storage_service.generate_job_id()
    
    # Encode image as base64 for Celery task
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    
    # Import and queue Celery task
    try:
        from app.tasks.localization_tasks import process_localization
        
        # Queue the task
        task = process_localization.delay(
            job_id=job_id,
            user_id=user_id,
            image_base64=image_base64,
            content_type=file.content_type or "image/png",
            target_languages=languages,
            target_markets=markets,
            source_language=source_language,
            preserve_faces=preserve_faces,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            remove_watermark=remove_watermark,
        )
        
        logger.info(f"📤 Queued job {job_id} (Celery task: {task.id})")
        
    except Exception as e:
        logger.error(f"Failed to queue task: {e}")
        raise HTTPException(
            status_code=503,
            detail="Failed to queue localization task. Please try again."
        )
    
    return {
        "job_id": job_id,
        "status": "queued",
        "message": f"Job queued for processing. Connect to WebSocket /ws/jobs/{job_id} for real-time updates.",
        "websocket_url": f"/ws/jobs/{job_id}",
        "target_languages": languages,
        "created_at": datetime.utcnow().isoformat(),
    }


@router.get(
    "/jobs/{job_id}/status",
    summary="Get job status",
    description="Get the current status of a localization job (polling fallback for WebSocket).",
)
async def get_job_status(job_id: str):
    """Get current job status from Redis."""
    try:
        from app.tasks.localization_tasks import job_status_store
        
        if job_id in job_status_store:
            return job_status_store[job_id]
        
        # Try to get from Redis
        import os
        from redis import Redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        redis_client = Redis.from_url(redis_url)
        
        # Check Celery result backend
        from app.core.celery_app import celery_app
        result = celery_app.AsyncResult(job_id)
        
        if result.state == "PENDING":
            return {
                "job_id": job_id,
                "status": "queued",
                "message": "Job is queued for processing",
            }
        elif result.state == "STARTED":
            return {
                "job_id": job_id,
                "status": "processing",
                "message": "Job is being processed",
            }
        elif result.state == "SUCCESS":
            return result.result
        elif result.state == "FAILURE":
            return {
                "job_id": job_id,
                "status": "failed",
                "error": str(result.result),
            }
        else:
            return {
                "job_id": job_id,
                "status": result.state.lower(),
                "message": f"Job state: {result.state}",
            }
            
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        return {
            "job_id": job_id,
            "status": "unknown",
            "message": "Could not retrieve job status",
        }


@router.get(
    "/languages",
    summary="Get supported languages",
    description="Get a list of all supported target languages for localization.",
)
async def get_supported_languages():
    """Get list of supported languages."""
    return {
        "languages": [
            {"code": lang.value, "name": lang.value.replace("_", " ").title()}
            for lang in TargetLanguage
        ]
    }


@router.get(
    "/markets",
    summary="Get supported markets",
    description="Get a list of all supported target markets for cultural adaptation.",
)
async def get_supported_markets():
    """Get list of supported markets."""
    return {
        "markets": [
            {"code": market.value, "name": market.value.replace("_", " ").title()}
            for market in TargetMarket
        ]
    }


@router.delete(
    "/{job_id}",
    summary="Delete job images",
    description="Delete all images associated with a localization job.",
)
async def delete_job(job_id: str):
    """Delete all images for a job."""
    storage_service = get_storage_service()
    
    if not storage_service.is_available:
        raise HTTPException(
            status_code=503,
            detail="Storage service not available"
        )
    
    deleted_count, error = await storage_service.delete_job_images(job_id)
    
    if error:
        raise HTTPException(status_code=500, detail=error)
    
    return {"message": f"Deleted {deleted_count} images for job {job_id}"}


@router.get(
    "/jobs/{user_id}",
    summary="Get user's localization jobs",
    description="Get all localization jobs for a specific user.",
)
async def get_user_jobs(
    user_id: str,
    limit: int = 50,
    offset: int = 0,
):
    """Get all localization jobs for a user."""
    supabase_service = get_supabase_service()
    
    if not supabase_service.is_available:
        raise HTTPException(
            status_code=503,
            detail="Database service not available"
        )
    
    jobs, error = await supabase_service.get_user_jobs(
        user_id=user_id,
        limit=limit,
        offset=offset,
    )
    
    if error:
        raise HTTPException(status_code=500, detail=error)
    
    return {"jobs": jobs, "count": len(jobs)}


@router.get(
    "/jobs/{user_id}/{job_id}",
    summary="Get a specific job",
    description="Get details of a specific localization job.",
)
async def get_job_details(
    user_id: str,
    job_id: str,
):
    """Get details of a specific job."""
    supabase_service = get_supabase_service()
    
    if not supabase_service.is_available:
        raise HTTPException(
            status_code=503,
            detail="Database service not available"
        )
    
    job, error = await supabase_service.get_job_by_id(
        job_id=job_id,
        user_id=user_id,
    )
    
    if error:
        raise HTTPException(status_code=500, detail=error)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job
