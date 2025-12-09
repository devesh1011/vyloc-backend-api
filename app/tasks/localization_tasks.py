"""
Localization Celery tasks.

Handles async image localization processing.
"""

import time
import logging
import asyncio
import json
import base64
from datetime import datetime
from typing import List, Dict, Any, Optional

from celery import current_task

from app.core.celery_app import celery_app
from app.services.gemini_service import get_gemini_service
from app.services.watermark_service import get_watermark_service
from app.services.storage_service import get_storage_service
from app.services.supabase_service import get_supabase_service
from app.schemas.localization import (
    TargetLanguage,
    TargetMarket,
    LocalizationStatus,
)

logger = logging.getLogger(__name__)

# In-memory job status store (for WebSocket updates)
# In production, you'd use Redis pub/sub for this
job_status_store: Dict[str, Dict[str, Any]] = {}


def update_job_status(job_id: str, status: Dict[str, Any]):
    """Update job status in the store and notify via Redis pub/sub."""
    job_status_store[job_id] = status
    
    # Publish to Redis for WebSocket subscribers
    try:
        from redis import Redis
        import os
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        redis_client = Redis.from_url(redis_url)
        redis_client.publish(f"job:{job_id}", json.dumps(status))
    except Exception as e:
        logger.warning(f"Failed to publish job status to Redis: {e}")


def run_async(coro):
    """Helper to run async functions in sync Celery context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="app.tasks.localization_tasks.process_localization")
def process_localization(
    self,
    job_id: str,
    user_id: str,
    image_base64: str,
    content_type: str,
    target_languages: List[str],
    target_markets: Optional[List[str]],
    source_language: str,
    preserve_faces: bool,
    aspect_ratio: Optional[str],
    image_size: str,
    remove_watermark: bool,
):
    """
    Process image localization asynchronously.
    
    This task:
    1. Uploads original image to GCS
    2. Generates localized versions using Gemini AI
    3. Removes watermarks from generated images
    4. Uploads results to GCS
    5. Saves job to Supabase
    6. Deducts user credits
    7. Sends real-time status updates via Redis pub/sub
    """
    start_time = time.time()
    
    logger.info(f"🚀 Starting localization task for job {job_id}")
    
    # Decode image
    image_bytes = base64.b64decode(image_base64)
    
    # Update status: started
    update_job_status(job_id, {
        "job_id": job_id,
        "status": "processing",
        "progress": 0,
        "message": "Starting localization...",
        "created_at": datetime.utcnow().isoformat(),
    })
    
    try:
        # Parse languages and markets
        languages = [TargetLanguage(lang) for lang in target_languages]
        markets = None
        if target_markets:
            markets = [TargetMarket(m) if m else None for m in target_markets]
        
        # Get services
        gemini_service = get_gemini_service()
        watermark_service = get_watermark_service()
        storage_service = get_storage_service()
        supabase_service = get_supabase_service()
        
        # Update status: uploading original
        update_job_status(job_id, {
            "job_id": job_id,
            "status": "processing",
            "progress": 10,
            "message": "Uploading original image...",
        })
        
        # Upload original image
        original_url = ""
        if storage_service.is_available:
            url, error = run_async(storage_service.upload_original_image(
                image_bytes=image_bytes,
                job_id=job_id,
                content_type=content_type,
            ))
            if url:
                original_url = url
                logger.info(f"✅ Original uploaded: {original_url}")
        
        # Update status: generating images
        update_job_status(job_id, {
            "job_id": job_id,
            "status": "processing",
            "progress": 20,
            "message": f"Generating {len(languages)} localized versions with AI...",
        })
        
        # Process localization
        localized_images = run_async(gemini_service.localize_image_batch(
            image_bytes=image_bytes,
            target_languages=languages,
            target_markets=markets,
            source_language=source_language,
            preserve_faces=preserve_faces,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        ))
        
        # Update status: post-processing
        update_job_status(job_id, {
            "job_id": job_id,
            "status": "processing",
            "progress": 60,
            "message": "Processing and uploading results...",
        })
        
        # Post-process: remove watermarks and upload IN PARALLEL
        async def process_single_image(img, idx):
            """Process a single image: remove watermark and upload."""
            if img.status != LocalizationStatus.COMPLETED:
                return img
            
            img_bytes = getattr(img, '_image_bytes', None)
            if not img_bytes:
                return img
            
            lang_name = img.language.value
            
            # Remove watermark if requested
            if remove_watermark:
                cleaned_bytes, error = await watermark_service.remove_watermark(img_bytes)
                if cleaned_bytes:
                    img_bytes = cleaned_bytes
                    logger.info(f"🧹 Watermark removed for {lang_name}")
            
            # Upload to storage
            if storage_service.is_available:
                url, error = await storage_service.upload_localized_image(
                    image_bytes=img_bytes,
                    job_id=job_id,
                    language=lang_name,
                )
                if url:
                    img.image_url = url
                    logger.info(f"✅ {lang_name} uploaded: {url}")
            
            # Clean up temporary bytes
            if hasattr(img, '_image_bytes'):
                delattr(img, '_image_bytes')
            
            return img
        
        # Run all post-processing in parallel
        async def process_all_images():
            tasks = [process_single_image(img, idx) for idx, img in enumerate(localized_images)]
            return await asyncio.gather(*tasks, return_exceptions=True)
        
        processed_results = run_async(process_all_images())
        
        # Handle results
        final_images = []
        for result in processed_results:
            if isinstance(result, Exception):
                logger.error(f"Post-processing error: {result}")
                # Keep original image with failed status
                final_images.append(localized_images[len(final_images)])
            else:
                final_images.append(result)
        
        # Calculate stats
        total_time_ms = int((time.time() - start_time) * 1000)
        completed_count = sum(1 for img in final_images if img.status == LocalizationStatus.COMPLETED)
        failed_count = sum(1 for img in final_images if img.status == LocalizationStatus.FAILED)
        
        # Determine overall status
        if failed_count == len(final_images):
            overall_status = "failed"
        elif completed_count == len(final_images):
            overall_status = "completed"
        else:
            overall_status = "completed"  # Partial success
        
        # Update status: saving to database
        update_job_status(job_id, {
            "job_id": job_id,
            "status": "processing",
            "progress": 95,
            "message": "Saving results...",
        })
        
        # Save to Supabase
        if supabase_service.is_available and completed_count > 0:
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
            
            success, error = run_async(supabase_service.save_localization_job(
                job_id=job_id,
                user_id=user_id,
                original_image_url=original_url,
                localized_images=localized_images_data,
                total_processing_time_ms=total_time_ms,
                target_languages=[img.language.value for img in final_images],
            ))
            
            if success:
                logger.info(f"💾 Job {job_id} saved to database")
                
                # Deduct credits
                run_async(supabase_service.deduct_credits(
                    user_id=user_id,
                    credits_to_deduct=completed_count,
                ))
                logger.info(f"💳 Deducted {completed_count} credits for user {user_id}")
        
        # Final result
        result = {
            "job_id": job_id,
            "status": overall_status,
            "progress": 100,
            "message": f"Completed! {completed_count} images generated.",
            "original_image_url": original_url,
            "localized_images": [
                {
                    "language": img.language.value if hasattr(img.language, 'value') else str(img.language),
                    "market": img.market.value if img.market and hasattr(img.market, 'value') else None,
                    "image_url": img.image_url,
                    "status": img.status.value if hasattr(img.status, 'value') else str(img.status),
                    "processing_time_ms": img.processing_time_ms,
                    "error_message": img.error_message,
                }
                for img in final_images
            ],
            "total_processing_time_ms": total_time_ms,
            "credits_used": completed_count,
            "completed_at": datetime.utcnow().isoformat(),
        }
        
        update_job_status(job_id, result)
        logger.info(f"✅ Job {job_id} completed in {total_time_ms}ms")
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Job {job_id} failed: {error_msg}")
        
        error_result = {
            "job_id": job_id,
            "status": "failed",
            "progress": 100,
            "message": f"Error: {error_msg}",
            "error": error_msg,
            "completed_at": datetime.utcnow().isoformat(),
        }
        
        update_job_status(job_id, error_result)
        
        # Re-raise for Celery retry logic
        raise
