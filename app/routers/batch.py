"""
Batch processing API router.

Provides endpoints for high-volume batch processing:
- Submit batch jobs
- Check job status
- List jobs
- Cancel jobs

Best for:
- Processing 100+ images
- Non-time-critical workflows
- Cost-optimized batch processing (50% lower cost)
- 24-hour turnaround jobs
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, HTTPException, status

from app.services.batch_service import (
    get_batch_service,
    BatchJobStatus,
    BatchJob,
)
from app.schemas.localization import TargetLanguage, TargetMarket


router = APIRouter(prefix="/batch", tags=["batch"])


# ============================================
# Request/Response Models
# ============================================

class BatchImageRequest(BaseModel):
    """Single image in a batch request."""
    image_gcs_uri: str = Field(
        ...,
        description="GCS URI of the image (e.g., gs://bucket/path/image.jpg)"
    )
    target_language: TargetLanguage
    target_market: Optional[TargetMarket] = None
    source_language: str = "english"
    preserve_faces: bool = False
    aspect_ratio: Optional[str] = None
    image_size: str = "1K"


class CreateBatchJobRequest(BaseModel):
    """Request to create a batch job."""
    requests: List[BatchImageRequest] = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="List of image localization requests"
    )
    input_gcs_uri: str = Field(
        ...,
        description="GCS URI for the input JSONL file"
    )
    output_gcs_uri: str = Field(
        ...,
        description="GCS URI prefix for output files"
    )
    metadata: Optional[dict] = None


class BatchJobResponse(BaseModel):
    """Response for a batch job."""
    job_id: str
    status: BatchJobStatus
    request_count: int
    created_at: str
    completed_at: Optional[str] = None
    results_gcs_uri: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[dict] = None


class BatchJobListResponse(BaseModel):
    """Response for listing batch jobs."""
    jobs: List[BatchJobResponse]
    total: int


# ============================================
# Helper Functions
# ============================================

def _batch_job_to_response(job: BatchJob) -> BatchJobResponse:
    """Convert BatchJob to API response."""
    return BatchJobResponse(
        job_id=job.job_id,
        status=job.status,
        request_count=len(job.requests),
        created_at=job.created_at.isoformat(),
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        results_gcs_uri=job.results_gcs_uri,
        error_message=job.error_message,
        metadata=job.metadata,
    )


# ============================================
# Endpoints
# ============================================

@router.post(
    "/jobs",
    response_model=BatchJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a batch job",
    description="""
    Submit a batch job for processing multiple images.
    
    Uses Gemini Batch API for cost-effective processing with ~24-hour turnaround.
    Best for processing 100+ images where real-time results aren't needed.
    
    **Pricing advantage**: Batch API costs 50% less than synchronous API.
    
    **Requirements**:
    - Images must be uploaded to GCS first
    - Input JSONL file will be created at the specified GCS URI
    - Results will be written to the output GCS URI prefix
    """,
)
async def create_batch_job(request: CreateBatchJobRequest) -> BatchJobResponse:
    """Create and submit a batch processing job."""
    batch_service = get_batch_service()
    
    if not batch_service.is_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Batch service is not available",
        )
    
    # Create batch requests
    batch_requests = [
        batch_service.create_batch_request(
            image_gcs_uri=req.image_gcs_uri,
            target_language=req.target_language,
            target_market=req.target_market,
            source_language=req.source_language,
            preserve_faces=req.preserve_faces,
            aspect_ratio=req.aspect_ratio,
            image_size=req.image_size,
        )
        for req in request.requests
    ]
    
    # Create JSONL file
    batch_service.create_jsonl_file(
        requests=batch_requests,
        output_gcs_uri=request.input_gcs_uri,
    )
    
    # Submit batch job
    job = await batch_service.submit_batch_job(
        requests=batch_requests,
        input_gcs_uri=request.input_gcs_uri,
        output_gcs_uri=request.output_gcs_uri,
        metadata=request.metadata,
    )
    
    return _batch_job_to_response(job)


@router.get(
    "/jobs/{job_id}",
    response_model=BatchJobResponse,
    summary="Get batch job status",
    description="Get the current status and details of a batch job.",
)
async def get_batch_job(job_id: str) -> BatchJobResponse:
    """Get the status of a batch job."""
    batch_service = get_batch_service()
    job = batch_service.get_job_status(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch job {job_id} not found",
        )
    
    return _batch_job_to_response(job)


@router.get(
    "/jobs",
    response_model=BatchJobListResponse,
    summary="List batch jobs",
    description="List all batch jobs, optionally filtered by status.",
)
async def list_batch_jobs(
    status_filter: Optional[BatchJobStatus] = None,
    limit: int = 100,
) -> BatchJobListResponse:
    """List batch jobs."""
    batch_service = get_batch_service()
    jobs = batch_service.list_jobs(status=status_filter, limit=limit)
    
    return BatchJobListResponse(
        jobs=[_batch_job_to_response(job) for job in jobs],
        total=len(jobs),
    )


@router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a batch job",
    description="Cancel a pending or processing batch job.",
)
async def cancel_batch_job(job_id: str) -> None:
    """Cancel a batch job."""
    batch_service = get_batch_service()
    success = await batch_service.cancel_job(job_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch job {job_id} not found or cannot be cancelled",
        )


@router.get(
    "/info",
    summary="Get batch API information",
    description="Get information about the batch processing API.",
)
async def get_batch_info() -> dict:
    """Get batch API information and guidelines."""
    batch_service = get_batch_service()
    
    return {
        "available": batch_service.is_available,
        "model": get_batch_service().settings.gemini_model,
        "pricing_advantage": "50% lower cost compared to synchronous API",
        "turnaround": "~24 hours",
        "max_requests_per_job": 10000,
        "supported_image_sizes": ["1K", "2K", "4K"],
        "supported_aspect_ratios": [
            "1:1", "2:3", "3:2", "3:4", "4:3", 
            "4:5", "5:4", "9:16", "16:9", "21:9"
        ],
        "when_to_use": [
            "Processing 100+ images",
            "Non-time-critical workflows",
            "Cost-optimized batch processing",
            "Overnight processing jobs",
        ],
        "when_not_to_use": [
            "Real-time/interactive use cases",
            "Single image processing",
            "Time-sensitive localizations (use /localize endpoint instead)",
        ],
    }
