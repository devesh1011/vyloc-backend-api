"""
Batch API Service for high-volume image localization.

Uses Google Gemini Batch API for processing large numbers of images
with 24-hour turnaround at 50% lower cost.

When to use:
- Processing 100+ images
- Non-time-critical batch jobs
- Cost optimization for large volumes
- Overnight processing workflows

When NOT to use:
- Real-time/interactive use cases
- Single image processing
- Time-sensitive localizations
"""

import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.schemas.localization import TargetLanguage, TargetMarket
from app.utils.prompts import build_localization_prompt


class BatchJobStatus(str, Enum):
    """Status of a batch job."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BatchRequest:
    """A single request in a batch job."""
    request_id: str
    image_gcs_uri: str  # gs://bucket/path/to/image.jpg
    target_language: TargetLanguage
    target_market: Optional[TargetMarket] = None
    source_language: str = "english"
    preserve_faces: bool = False
    aspect_ratio: Optional[str] = None
    image_size: str = "1K"


@dataclass
class BatchJob:
    """A batch processing job."""
    job_id: str
    status: BatchJobStatus
    requests: List[BatchRequest]
    created_at: datetime
    completed_at: Optional[datetime] = None
    results_gcs_uri: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BatchService:
    """
    Service for batch processing of image localizations.
    
    Uses Gemini Batch API for high-volume, cost-effective processing.
    Results are stored in GCS and can be retrieved after job completion.
    """
    
    def __init__(self):
        """Initialize the batch service."""
        self.settings = get_settings()
        self.client: Any = None
        self._initialize_client()
        self._jobs: Dict[str, BatchJob] = {}  # In-memory job tracking (use DB in production)
    
    def _initialize_client(self):
        """Initialize the Gemini API client."""
        if self.settings.google_api_key:
            self.client = genai.Client(api_key=self.settings.google_api_key)
        else:
            try:
                self.client = genai.Client()
            except Exception:
                self.client = None
    
    @property
    def is_available(self) -> bool:
        """Check if batch service is available."""
        return self.client is not None
    
    def create_batch_request(
        self,
        image_gcs_uri: str,
        target_language: TargetLanguage,
        target_market: Optional[TargetMarket] = None,
        source_language: str = "english",
        preserve_faces: bool = False,
        aspect_ratio: Optional[str] = None,
        image_size: str = "1K",
    ) -> BatchRequest:
        """Create a single batch request."""
        return BatchRequest(
            request_id=str(uuid.uuid4()),
            image_gcs_uri=image_gcs_uri,
            target_language=target_language,
            target_market=target_market,
            source_language=source_language,
            preserve_faces=preserve_faces,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )
    
    def _build_batch_request_body(self, request: BatchRequest) -> Dict[str, Any]:
        """Build the request body for a single batch request."""
        prompt = build_localization_prompt(
            target_language=request.target_language,
            target_market=request.target_market,
            source_language=request.source_language,
            preserve_faces=request.preserve_faces,
        )
        
        # Build image config
        image_config: Dict[str, Any] = {
            "image_size": request.image_size.upper(),
        }
        if request.aspect_ratio:
            image_config["aspect_ratio"] = request.aspect_ratio
        
        return {
            "custom_id": request.request_id,
            "model": self.settings.gemini_model,
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {"file_data": {"file_uri": request.image_gcs_uri}}
                    ]
                }
            ],
            "config": {
                "response_modalities": ["TEXT", "IMAGE"],
                "image_config": image_config,
            }
        }
    
    def create_jsonl_file(
        self,
        requests: List[BatchRequest],
        output_gcs_uri: str,
    ) -> str:
        """
        Create a JSONL file for batch processing.
        
        In production, this would upload to GCS.
        Returns the GCS URI of the JSONL file.
        
        Args:
            requests: List of batch requests
            output_gcs_uri: GCS path for the JSONL file (e.g., gs://bucket/batch/input.jsonl)
            
        Returns:
            The GCS URI of the created JSONL file
        """
        # Build JSONL content - each line is a JSON object
        _jsonl_content = "\n".join(
            json.dumps(self._build_batch_request_body(req))
            for req in requests
        )
        
        # TODO: Upload to GCS using storage_service
        # storage_service.upload_text(_jsonl_content, output_gcs_uri)
        
        return output_gcs_uri
    
    async def submit_batch_job(
        self,
        requests: List[BatchRequest],
        input_gcs_uri: str,
        output_gcs_uri: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BatchJob:
        """
        Submit a batch job for processing.
        
        Note: This requires Vertex AI Batch Prediction API.
        The Gemini Batch API processes requests asynchronously with 24-hour turnaround.
        
        Args:
            requests: List of batch requests
            input_gcs_uri: GCS URI of the input JSONL file
            output_gcs_uri: GCS URI prefix for output files
            metadata: Optional metadata to attach to the job
            
        Returns:
            BatchJob object with job tracking information
        """
        if not self.client:
            raise RuntimeError("Batch service client not initialized")
        
        job_id = str(uuid.uuid4())
        
        # Create job record
        job = BatchJob(
            job_id=job_id,
            status=BatchJobStatus.PENDING,
            requests=requests,
            created_at=datetime.utcnow(),
            results_gcs_uri=output_gcs_uri,
            metadata=metadata or {},
        )
        
        # Store job (in production, use database)
        self._jobs[job_id] = job
        
        try:
            # Create batch job using Gemini Batch API
            # Note: This uses the batches API from google-genai
            batch_job = self.client.batches.create(
                model=self.settings.gemini_model,
                src=input_gcs_uri,
                dest=output_gcs_uri,
                config=types.CreateBatchJobConfig(
                    display_name=f"vyloc-batch-{job_id[:8]}",
                )
            )
            
            # Update job with API response
            job.status = BatchJobStatus.PROCESSING
            job.metadata["api_job_name"] = batch_job.name
            
        except Exception as e:
            job.status = BatchJobStatus.FAILED
            job.error_message = str(e)
        
        return job
    
    def get_job_status(self, job_id: str) -> Optional[BatchJob]:
        """Get the status of a batch job."""
        job = self._jobs.get(job_id)
        
        if job and job.status == BatchJobStatus.PROCESSING:
            # Check API for updated status
            api_job_name = job.metadata.get("api_job_name")
            if api_job_name and self.client:
                try:
                    batch_job = self.client.batches.get(name=api_job_name)
                    
                    # Map API status to our status
                    api_state = getattr(batch_job, 'state', None)
                    if api_state:
                        state_str = str(api_state).upper()
                        if "SUCCEEDED" in state_str:
                            job.status = BatchJobStatus.COMPLETED
                            job.completed_at = datetime.utcnow()
                        elif "FAILED" in state_str:
                            job.status = BatchJobStatus.FAILED
                        elif "CANCELLED" in state_str:
                            job.status = BatchJobStatus.CANCELLED
                            
                except Exception as e:
                    # Log error but don't fail
                    job.metadata["status_check_error"] = str(e)
        
        return job
    
    def list_jobs(
        self,
        status: Optional[BatchJobStatus] = None,
        limit: int = 100,
    ) -> List[BatchJob]:
        """List batch jobs, optionally filtered by status."""
        jobs = list(self._jobs.values())
        
        if status:
            jobs = [j for j in jobs if j.status == status]
        
        # Sort by created_at descending
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        
        return jobs[:limit]
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or processing batch job."""
        job = self._jobs.get(job_id)
        
        if not job:
            return False
        
        if job.status not in [BatchJobStatus.PENDING, BatchJobStatus.PROCESSING]:
            return False
        
        # Cancel via API
        api_job_name = job.metadata.get("api_job_name")
        if api_job_name and self.client:
            try:
                self.client.batches.cancel(name=api_job_name)
            except Exception:
                pass
        
        job.status = BatchJobStatus.CANCELLED
        return True


# Singleton instance
_batch_service: Optional[BatchService] = None


def get_batch_service() -> BatchService:
    """Get or create the batch service singleton."""
    global _batch_service
    if _batch_service is None:
        _batch_service = BatchService()
    return _batch_service
