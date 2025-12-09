from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # App Configuration
    app_name: str = "Vyloc API"
    app_version: str = "0.1.0"
    debug: bool = False
    env: str = "development"
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # CORS Configuration - stored as comma-separated string
    cors_origins_str: str = "http://localhost:3000,http://localhost:8000,https://adaptly-five.vercel.app,https://*.ngrok-free.app"
    
    # Google AI Configuration
    google_api_key: str = ""
    gemini_model: str = "gemini-3-pro-image-preview"
    default_image_resolution: str = "2K"  # 1K, 2K, 4K
    default_aspect_ratio: str = "1:1"  # 1:1, 9:16, 16:9, 3:4, 4:3
    
    # Vertex AI Configuration (required for gemini-3-pro-image-preview)
    use_vertex_ai: bool = True
    vertex_ai_project: str = ""
    vertex_ai_location: str = "global"
    
    # Google Cloud Storage Configuration
    gcs_bucket_name: str = ""
    gcs_project_id: str = ""
    gcs_credentials_path: str = ""
    
    # Supabase Configuration
    supabase_url: str = ""
    supabase_key: str = ""
    
    # Image Processing Configuration
    max_image_size_mb: int = 10
    supported_formats_str: str = "image/jpeg,image/png,image/webp"
    default_output_format: str = "image/png"
    default_image_quality: int = 95
    
    @property
    def cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins_str.split(",") if origin.strip()]
    
    @property
    def supported_image_formats(self) -> List[str]:
        """Parse supported image formats from comma-separated string."""
        return [fmt.strip() for fmt in self.supported_formats_str.split(",") if fmt.strip()]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
