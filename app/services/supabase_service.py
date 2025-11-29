"""
Supabase Service for database operations.

Handles saving localization jobs and managing user credits.
"""

import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from supabase import create_client, Client

logger = logging.getLogger(__name__)

# Environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


class SupabaseService:
    """Service for Supabase database operations."""
    
    def __init__(self):
        """Initialize the Supabase client."""
        self.client: Optional[Client] = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the Supabase client with service role key."""
        try:
            if not SUPABASE_URL:
                logger.warning("⚠️ SUPABASE_URL not configured")
                return
            
            # Prefer service key for admin operations
            key = SUPABASE_SERVICE_KEY or SUPABASE_KEY
            if not key:
                logger.warning("⚠️ No Supabase key configured")
                return
            
            self.client = create_client(SUPABASE_URL, key)
            logger.info("✅ Supabase client initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Supabase client: {e}")
            self.client = None
    
    @property
    def is_available(self) -> bool:
        """Check if Supabase service is available."""
        return self.client is not None
    
    async def save_localization_job(
        self,
        job_id: str,
        user_id: str,
        original_image_url: str,
        localized_images: List[Dict[str, Any]],
        total_processing_time_ms: int,
        target_languages: List[str],
    ) -> tuple[bool, Optional[str]]:
        """
        Save a localization job to the database.
        
        Args:
            job_id: Unique job identifier
            user_id: User's Supabase auth ID
            original_image_url: URL of the original uploaded image
            localized_images: List of localized image data
            total_processing_time_ms: Total processing time in milliseconds
            target_languages: List of target languages
            
        Returns:
            Tuple of (success, error_message)
        """
        if not self.is_available:
            return False, "Supabase not configured"
        
        try:
            # Prepare job data matching the actual schema
            # Don't include 'id' - let Supabase auto-generate the UUID
            job_data = {
                "user_id": user_id,
                "source_image_url": original_image_url,
                "target_languages": target_languages,
                "result_images": localized_images,
                "processing_time_ms": total_processing_time_ms,
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
            }
            
            # Insert into localization_jobs table
            result = self.client.table("localization_jobs").insert(job_data).execute()
            
            if result.data:
                db_id = result.data[0].get("id", job_id)
                logger.info(f"✅ Saved job {db_id} to Supabase")
                return True, None
            else:
                return False, "Failed to insert job data"
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Failed to save job {job_id}: {error_msg}")
            return False, error_msg
    
    async def check_credits_available(
        self,
        user_id: str,
        credits_required: int,
    ) -> tuple[bool, int, Optional[str]]:
        """
        Check if user has enough credits for the operation.
        
        Args:
            user_id: User's Supabase auth ID
            credits_required: Number of credits needed
            
        Returns:
            Tuple of (has_enough, credits_remaining, error_message)
        """
        if not self.is_available:
            return False, 0, "Supabase not configured"
        
        try:
            # Get current subscription
            result = self.client.table("subscriptions").select("*").eq("user_id", user_id).eq("status", "active").single().execute()
            
            if not result.data:
                return False, 0, "No active subscription found"
            
            monthly_limit = result.data.get("monthly_credit_limit", 0)
            credits_used = result.data.get("credits_used", 0)
            credits_remaining = monthly_limit - credits_used
            
            if credits_remaining < credits_required:
                return False, credits_remaining, f"Insufficient credits. Required: {credits_required}, Available: {credits_remaining}"
            
            return True, credits_remaining, None
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Failed to check credits for user {user_id}: {error_msg}")
            return False, 0, error_msg

    async def deduct_credits(
        self,
        user_id: str,
        credits_to_deduct: int,
    ) -> tuple[bool, Optional[str]]:
        """
        Deduct credits from user's subscription.
        
        Args:
            user_id: User's Supabase auth ID
            credits_to_deduct: Number of credits to deduct
            
        Returns:
            Tuple of (success, error_message)
        """
        if not self.is_available:
            return False, "Supabase not configured"
        
        try:
            # Get current subscription
            result = self.client.table("subscriptions").select("*").eq("user_id", user_id).eq("status", "active").single().execute()
            
            if not result.data:
                return False, "No active subscription found"
            
            current_credits_used = result.data.get("credits_used", 0)
            new_credits_used = current_credits_used + credits_to_deduct
            
            # Update credits_used
            update_result = self.client.table("subscriptions").update({
                "credits_used": new_credits_used,
            }).eq("user_id", user_id).eq("status", "active").execute()
            
            if update_result.data:
                logger.info(f"✅ Deducted {credits_to_deduct} credits for user {user_id}. New total used: {new_credits_used}")
                return True, None
            else:
                return False, "Failed to update credits"
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Failed to deduct credits for user {user_id}: {error_msg}")
            return False, error_msg
    
    async def get_user_jobs(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Get user's localization jobs.
        
        Args:
            user_id: User's Supabase auth ID
            limit: Maximum number of jobs to return
            offset: Offset for pagination
            
        Returns:
            Tuple of (jobs_list, error_message)
        """
        if not self.is_available:
            return [], "Supabase not configured"
        
        try:
            result = self.client.table("localization_jobs").select("*").eq("user_id", user_id).order("created_at", desc=True).range(offset, offset + limit - 1).execute()
            
            return result.data or [], None
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Failed to get jobs for user {user_id}: {error_msg}")
            return [], error_msg
    
    async def get_job_by_id(
        self,
        job_id: str,
        user_id: str,
    ) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Get a specific job by ID.
        
        Args:
            job_id: Job identifier
            user_id: User's Supabase auth ID (for authorization)
            
        Returns:
            Tuple of (job_data, error_message)
        """
        if not self.is_available:
            return None, "Supabase not configured"
        
        try:
            result = self.client.table("localization_jobs").select("*").eq("id", job_id).eq("user_id", user_id).single().execute()
            
            return result.data, None
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Failed to get job {job_id}: {error_msg}")
            return None, error_msg


# Singleton instance
_supabase_service: Optional[SupabaseService] = None


def get_supabase_service() -> SupabaseService:
    """Get the singleton Supabase service instance."""
    global _supabase_service
    if _supabase_service is None:
        _supabase_service = SupabaseService()
    return _supabase_service
