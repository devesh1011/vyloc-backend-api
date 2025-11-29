from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
from datetime import datetime


class TargetLanguage(str, Enum):
    """Supported target languages for localization."""
    HINDI = "hindi"
    JAPANESE = "japanese"
    KOREAN = "korean"
    GERMAN = "german"
    FRENCH = "french"
    SPANISH = "spanish"
    ITALIAN = "italian"
    PORTUGUESE = "portuguese"
    CHINESE_SIMPLIFIED = "chinese_simplified"
    CHINESE_TRADITIONAL = "chinese_traditional"
    ARABIC = "arabic"
    RUSSIAN = "russian"
    THAI = "thai"
    VIETNAMESE = "vietnamese"
    INDONESIAN = "indonesian"


class TargetMarket(str, Enum):
    """Target markets for cultural adaptation."""
    INDIA = "india"
    JAPAN = "japan"
    SOUTH_KOREA = "south_korea"
    GERMANY = "germany"
    FRANCE = "france"
    SPAIN = "spain"
    ITALY = "italy"
    BRAZIL = "brazil"
    CHINA = "china"
    TAIWAN = "taiwan"
    MIDDLE_EAST = "middle_east"
    RUSSIA = "russia"
    THAILAND = "thailand"
    VIETNAM = "vietnam"
    INDONESIA = "indonesia"
    USA = "usa"
    UK = "uk"


class LocalizationStatus(str, Enum):
    """Status of a localization job."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class LocalizationRequest(BaseModel):
    """Request schema for image localization."""
    target_languages: List[TargetLanguage] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of target languages for localization"
    )
    target_markets: Optional[List[TargetMarket]] = Field(
        default=None,
        description="Target markets for cultural adaptation (optional, will be inferred from languages if not provided)"
    )
    source_language: Optional[str] = Field(
        default="english",
        description="Source language of the ad image (auto-detected if not provided)"
    )
    preserve_faces: bool = Field(
        default=False,
        description="If True, preserve original faces; if False, adapt faces to target market demographics"
    )
    aspect_ratio: Optional[str] = Field(
        default=None,
        description="Output aspect ratio (e.g., '16:9', '1:1', '9:16'). If not provided, matches source image."
    )
    image_size: Optional[str] = Field(
        default="1K",
        description="Output image size: '1K', '2K', or '4K'"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "target_languages": ["hindi", "japanese", "german"],
                "target_markets": ["india", "japan", "germany"],
                "source_language": "english",
                "preserve_faces": False,
                "image_size": "2K"
            }
        }


class LocalizedImage(BaseModel):
    """Schema for a single localized image result."""
    language: TargetLanguage
    market: Optional[TargetMarket] = None
    image_url: str = Field(..., description="URL of the localized image in GCS")
    thumbnail_url: Optional[str] = Field(default=None, description="Thumbnail URL")
    status: LocalizationStatus = LocalizationStatus.COMPLETED
    error_message: Optional[str] = None
    processing_time_ms: Optional[int] = None


class LocalizationResponse(BaseModel):
    """Response schema for localization job."""
    job_id: str = Field(..., description="Unique identifier for the localization job")
    status: LocalizationStatus
    original_image_url: str = Field(..., description="URL of the original uploaded image")
    localized_images: List[LocalizedImage] = Field(
        default=[],
        description="List of localized images"
    )
    total_processing_time_ms: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "abc123",
                "status": "completed",
                "original_image_url": "https://storage.googleapis.com/vyloc/original/abc123.png",
                "localized_images": [
                    {
                        "language": "hindi",
                        "market": "india",
                        "image_url": "https://storage.googleapis.com/vyloc/localized/abc123_hindi.png",
                        "status": "completed",
                        "processing_time_ms": 3500
                    }
                ],
                "total_processing_time_ms": 5000,
                "created_at": "2025-11-26T10:00:00Z",
                "completed_at": "2025-11-26T10:00:05Z"
            }
        }


class JobStatusResponse(BaseModel):
    """Response schema for job status check."""
    job_id: str
    status: LocalizationStatus
    progress: float = Field(
        ...,
        ge=0,
        le=100,
        description="Progress percentage (0-100)"
    )
    completed_languages: List[TargetLanguage] = []
    pending_languages: List[TargetLanguage] = []
    failed_languages: List[TargetLanguage] = []
    error_message: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    message: str = "Vyloc API is running"
    version: str
    gemini_available: bool = False
    gcs_available: bool = False
    batch_available: bool = False
