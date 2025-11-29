"""
Google Cloud Storage Service for image storage.

Handles uploading, downloading, and managing images in GCS buckets.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple

from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError

from app.core.config import get_settings


class StorageService:
    """
    Service for managing image storage in Google Cloud Storage.
    
    Handles:
    - Uploading original images
    - Uploading localized images
    - Generating signed URLs for access
    - Organizing images by job ID and language
    """
    
    def __init__(self):
        """Initialize the GCS client."""
        self.settings = get_settings()
        self.client: Optional[storage.Client] = None
        self.bucket: Optional[storage.Bucket] = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the GCS client and bucket."""
        try:
            if self.settings.gcs_credentials_path:
                self.client = storage.Client.from_service_account_json(
                    self.settings.gcs_credentials_path
                )
            else:
                # Use default credentials (ADC)
                self.client = storage.Client(
                    project=self.settings.gcs_project_id if self.settings.gcs_project_id else None
                )
            
            if self.settings.gcs_bucket_name:
                self.bucket = self.client.bucket(self.settings.gcs_bucket_name)
        except Exception:
            self.client = None
            self.bucket = None
    
    @property
    def is_available(self) -> bool:
        """Check if GCS storage is available."""
        return self.client is not None and self.bucket is not None
    
    def generate_job_id(self) -> str:
        """Generate a unique job ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        return f"{timestamp}_{unique_id}"
    
    async def upload_original_image(
        self,
        image_bytes: bytes,
        job_id: str,
        content_type: str = "image/png",
        filename: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Upload the original image to GCS.
        
        Args:
            image_bytes: Image data as bytes
            job_id: Unique job identifier
            content_type: MIME type of the image
            filename: Optional original filename
            
        Returns:
            Tuple of (public_url, error_message)
        """
        if not self.is_available:
            return None, "GCS storage not configured"
        
        try:
            # Determine file extension
            ext = self._get_extension_from_content_type(content_type)
            
            # Create blob path
            blob_path = f"originals/{job_id}/original{ext}"
            
            result = await asyncio.to_thread(
                self._upload_blob_sync,
                blob_path,
                image_bytes,
                content_type,
            )
            return result
        except Exception as e:
            return None, f"Upload error: {str(e)}"
    
    async def upload_localized_image(
        self,
        image_bytes: bytes,
        job_id: str,
        language: str,
        content_type: str = "image/png",
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Upload a localized image to GCS.
        
        Args:
            image_bytes: Image data as bytes
            job_id: Unique job identifier
            language: Target language code
            content_type: MIME type of the image
            
        Returns:
            Tuple of (public_url, error_message)
        """
        if not self.is_available:
            return None, "GCS storage not configured"
        
        try:
            ext = self._get_extension_from_content_type(content_type)
            blob_path = f"localized/{job_id}/{language}{ext}"
            
            result = await asyncio.to_thread(
                self._upload_blob_sync,
                blob_path,
                image_bytes,
                content_type,
            )
            return result
        except Exception as e:
            return None, f"Upload error: {str(e)}"
    
    def _upload_blob_sync(
        self,
        blob_path: str,
        data: bytes,
        content_type: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Synchronous blob upload implementation."""
        try:
            if not self.bucket:
                return None, "Bucket not initialized"
            
            blob = self.bucket.blob(blob_path)
            blob.upload_from_string(data, content_type=content_type)
            
            # Try to make the blob publicly accessible
            # This will fail if uniform bucket-level access is enabled, but that's OK
            try:
                blob.make_public()
            except Exception:
                # If make_public fails (uniform bucket access), construct public URL directly
                # The URL will work if the bucket/object is publicly readable
                pass
            
            # Construct the public URL
            # Format: https://storage.googleapis.com/bucket-name/blob-path
            public_url = f"https://storage.googleapis.com/{self.bucket.name}/{blob_path}"
            return public_url, None
        except GoogleCloudError as e:
            return None, f"GCS error: {str(e)}"
    
    async def get_signed_url(
        self,
        blob_path: str,
        expiration_hours: int = 24,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Generate a signed URL for private blob access.
        
        Args:
            blob_path: Path to the blob in GCS
            expiration_hours: URL expiration time in hours
            
        Returns:
            Tuple of (signed_url, error_message)
        """
        if not self.is_available:
            return None, "GCS storage not configured"
        
        try:
            result = await asyncio.to_thread(
                self._get_signed_url_sync,
                blob_path,
                expiration_hours,
            )
            return result
        except Exception as e:
            return None, f"Signed URL error: {str(e)}"
    
    def _get_signed_url_sync(
        self,
        blob_path: str,
        expiration_hours: int,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Synchronous signed URL generation."""
        try:
            if not self.bucket:
                return None, "Bucket not initialized"
            
            blob = self.bucket.blob(blob_path)
            
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(hours=expiration_hours),
                method="GET",
            )
            
            return url, None
        except GoogleCloudError as e:
            return None, f"GCS error: {str(e)}"
    
    async def delete_job_images(self, job_id: str) -> Tuple[int, Optional[str]]:
        """
        Delete all images associated with a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Tuple of (deleted_count, error_message)
        """
        if not self.is_available:
            return 0, "GCS storage not configured"
        
        try:
            result = await asyncio.to_thread(
                self._delete_job_images_sync,
                job_id,
            )
            return result
        except Exception as e:
            return 0, f"Delete error: {str(e)}"
    
    def _delete_job_images_sync(self, job_id: str) -> Tuple[int, Optional[str]]:
        """Synchronous job image deletion."""
        try:
            if not self.bucket:
                return 0, "Bucket not initialized"
            
            deleted_count = 0
            
            # Delete original images
            original_prefix = f"originals/{job_id}/"
            for blob in self.bucket.list_blobs(prefix=original_prefix):
                blob.delete()
                deleted_count += 1
            
            # Delete localized images
            localized_prefix = f"localized/{job_id}/"
            for blob in self.bucket.list_blobs(prefix=localized_prefix):
                blob.delete()
                deleted_count += 1
            
            return deleted_count, None
        except GoogleCloudError as e:
            return 0, f"GCS error: {str(e)}"
    
    def _get_extension_from_content_type(self, content_type: str) -> str:
        """Get file extension from content type."""
        mapping = {
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }
        return mapping.get(content_type, ".png")


# Singleton instance
_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Get or create the storage service singleton."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
