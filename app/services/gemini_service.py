"""
Gemini AI Service for image localization.

Handles parallel processing of multiple language localizations using Google's Gemini API.
Uses Gemini 3 Pro Image (gemini-3-pro-image-preview) for state-of-the-art image generation.

Features:
- High-resolution output: 1K, 2K, and 4K visuals
- Advanced text rendering for marketing assets
- Thinking mode for complex prompt reasoning
- Up to 14 reference images support
"""

import asyncio
import time
import logging
from io import BytesIO
from typing import List, Optional, Tuple, Any
from PIL import Image

from google import genai
from google.genai import types

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

from app.core.config import get_settings
from app.schemas.localization import (
    TargetLanguage,
    TargetMarket,
    LocalizedImage,
    LocalizationStatus,
)
from app.utils.prompts import build_localization_prompt, LANGUAGE_TO_DEFAULT_MARKET


# Valid aspect ratios for Gemini 3 Pro Image
VALID_ASPECT_RATIOS = ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]

# Valid image sizes (must be uppercase K)
VALID_IMAGE_SIZES = ["1K", "2K", "4K"]


class GeminiService:
    """Service for interacting with Google's Gemini API for image localization."""
    
    def __init__(self):
        """Initialize the Gemini client."""
        self.settings = get_settings()
        self.client: Any = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the Gemini API client."""
        try:
            if self.settings.use_vertex_ai and self.settings.vertex_ai_project:
                # Use Vertex AI (required for gemini-3-pro-image-preview)
                # SDK v1.52+ doesn't allow api_key with vertexai - uses ADC instead
                self.client = genai.Client(
                    vertexai=True,
                    project=self.settings.vertex_ai_project,
                    location=self.settings.vertex_ai_location or "global",
                )
                logger.info(f"✅ Initialized Vertex AI client for project: {self.settings.vertex_ai_project}")
            elif self.settings.google_api_key:
                # Use regular Gemini API (for models like gemini-2.0-flash-exp-image-generation)
                self.client = genai.Client(api_key=self.settings.google_api_key)
                logger.info("✅ Initialized Gemini API client")
            else:
                self.client = genai.Client()
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini client: {e}")
            self.client = None
    
    @property
    def is_available(self) -> bool:
        """Check if Gemini service is available."""
        return self.client is not None
    
    def _validate_image_size(self, size: str) -> str:
        """Validate and normalize image size. Must be uppercase K."""
        size_upper = size.upper()
        if size_upper not in VALID_IMAGE_SIZES:
            return "1K"  # Default to 1K
        return size_upper
    
    def _validate_aspect_ratio(self, ratio: Optional[str]) -> Optional[str]:
        """Validate aspect ratio."""
        if ratio and ratio in VALID_ASPECT_RATIOS:
            return ratio
        return None
    
    async def localize_image(
        self,
        image_bytes: bytes,
        target_language: TargetLanguage,
        target_market: Optional[TargetMarket] = None,
        source_language: str = "english",
        preserve_faces: bool = False,
        aspect_ratio: Optional[str] = None,
        image_size: str = "1K",
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Localize a single image to a target language/market using Gemini 3 Pro Image.
        
        Args:
            image_bytes: Original image as bytes
            target_language: Target language for text translation
            target_market: Target market for cultural adaptation
            source_language: Source language of original image
            preserve_faces: Whether to preserve original faces
            aspect_ratio: Output aspect ratio (1:1, 16:9, 9:16, etc.)
            image_size: Output image size (1K, 2K, 4K) - must be uppercase K
            
        Returns:
            Tuple of (localized_image_bytes, error_message)
        """
        if not self.client:
            return None, "Gemini client not initialized"
        
        try:
            # Build the prompt
            prompt = build_localization_prompt(
                target_language=target_language,
                target_market=target_market,
                source_language=source_language,
                preserve_faces=preserve_faces,
            )
            
            # Load image from bytes
            image = Image.open(BytesIO(image_bytes))
            
            # Validate and build image config
            validated_size = self._validate_image_size(image_size)
            validated_ratio = self._validate_aspect_ratio(aspect_ratio)
            
            # Build ImageConfig for Gemini 3 Pro Image
            # Note: Using dict-based config for broader SDK compatibility
            image_config_dict: dict[str, Any] = {
                "image_size": validated_size,
            }
            if validated_ratio:
                image_config_dict["aspect_ratio"] = validated_ratio
            
            # Build generation config
            # Try to use ImageConfig type if available, fallback to dict
            try:
                image_config = types.ImageConfig(**image_config_dict)  # type: ignore[attr-defined]
            except (AttributeError, TypeError):
                # Fallback for older SDK versions
                image_config = image_config_dict  # type: ignore
            
            generation_config = types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                image_config=image_config,  # type: ignore - SDK types may not be updated
            )
            
            # Generate localized image using Gemini 3 Pro Image
            logger.info(f"🎨 Generating image for {target_language.value} using {self.settings.gemini_model}")
            start_time = time.time()
            
            try:
                # Add timeout to prevent infinite hanging
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.models.generate_content,
                        model=self.settings.gemini_model,
                        contents=[prompt, image],
                        config=generation_config,
                    ),
                    timeout=120.0  # 2 minute timeout
                )
                logger.info(f"✅ Got response for {target_language.value} in {time.time() - start_time:.2f}s")
            except asyncio.TimeoutError:
                logger.error(f"⏰ Timeout for {target_language.value} after 120 seconds")
                return None, "Request timed out after 120 seconds"
            
            # Extract image from response (skip thought images, get final output)
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    # Iterate through parts, looking for the final non-thought image
                    final_image_bytes = None
                    for part in candidate.content.parts:
                        # Skip thought parts (interim reasoning images)
                        if hasattr(part, 'thought') and part.thought:
                            continue
                        
                        # Check for image data
                        if hasattr(part, 'inline_data') and part.inline_data is not None:
                            final_image_bytes = part.inline_data.data
                        
                        # Also check as_image() method
                        elif hasattr(part, 'as_image'):
                            try:
                                img = part.as_image()
                                if img:
                                    # Convert PIL Image to bytes
                                    buffer = BytesIO()
                                    img.save(buffer, format='PNG')
                                    final_image_bytes = buffer.getvalue()
                            except Exception:
                                pass
                    
                    if final_image_bytes:
                        return final_image_bytes, None
            
            return None, "No image generated in response"
            
        except Exception as e:
            return None, f"Gemini API error: {str(e)}"
    
    async def localize_image_batch(
        self,
        image_bytes: bytes,
        target_languages: List[TargetLanguage],
        target_markets: Optional[List[Optional[TargetMarket]]] = None,
        source_language: str = "english",
        preserve_faces: bool = False,
        aspect_ratio: Optional[str] = None,
        image_size: str = "1K",
    ) -> List[LocalizedImage]:
        """
        Localize an image to multiple languages in parallel.
        
        Args:
            image_bytes: Original image as bytes
            target_languages: List of target languages
            target_markets: List of target markets (optional, will be inferred)
            source_language: Source language of original image
            preserve_faces: Whether to preserve original faces
            aspect_ratio: Output aspect ratio
            image_size: Output image size
            
        Returns:
            List of LocalizedImage results
        """
        # Create market mapping
        markets_list: List[Optional[TargetMarket]]
        if target_markets is None:
            markets_list = [None] * len(target_languages)
        elif len(target_markets) != len(target_languages):
            # Pad or truncate to match
            markets_list = list(target_markets) + [None] * (len(target_languages) - len(target_markets))
            markets_list = markets_list[:len(target_languages)]
        else:
            markets_list = list(target_markets)
        
        # Create async tasks for parallel processing
        tasks = []
        start_times: dict[int, float] = {}
        
        for i, (language, market) in enumerate(zip(target_languages, markets_list)):
            start_times[i] = time.time()
            task = self.localize_image(
                image_bytes=image_bytes,
                target_language=language,
                target_market=market,
                source_language=source_language,
                preserve_faces=preserve_faces,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
            )
            tasks.append(task)
        
        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        localized_images: List[LocalizedImage] = []
        
        for i, (language, result) in enumerate(zip(target_languages, results)):
            processing_time = int((time.time() - start_times[i]) * 1000)
            market = markets_list[i] if markets_list[i] else LANGUAGE_TO_DEFAULT_MARKET.get(language)
            
            if isinstance(result, Exception):
                localized_images.append(LocalizedImage(
                    language=language,
                    market=market,
                    image_url="",
                    status=LocalizationStatus.FAILED,
                    error_message=str(result),
                    processing_time_ms=processing_time,
                ))
            elif isinstance(result, tuple):
                image_bytes_result, error = result
                if error:
                    localized_images.append(LocalizedImage(
                        language=language,
                        market=market,
                        image_url="",
                        status=LocalizationStatus.FAILED,
                        error_message=error,
                        processing_time_ms=processing_time,
                    ))
                else:
                    # Create result with temporary bytes storage
                    img_result = LocalizedImage(
                        language=language,
                        market=market,
                        image_url="",  # Will be set after GCS upload
                        status=LocalizationStatus.COMPLETED,
                        processing_time_ms=processing_time,
                    )
                    # Store bytes as a dynamic attribute for later processing
                    setattr(img_result, '_image_bytes', image_bytes_result)
                    localized_images.append(img_result)
            else:
                localized_images.append(LocalizedImage(
                    language=language,
                    market=market,
                    image_url="",
                    status=LocalizationStatus.FAILED,
                    error_message="Unexpected result type",
                    processing_time_ms=processing_time,
                ))
        
        return localized_images


# Singleton instance
_gemini_service: Optional[GeminiService] = None


def get_gemini_service() -> GeminiService:
    """Get or create the Gemini service singleton."""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service
