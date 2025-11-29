"""
Watermark Removal Service using Neural Network.

Uses FODUU AI's Watermark Removal model for high-quality watermark removal.
Model: https://huggingface.co/foduucom/Watermark_Removal

Strategy: Only process the watermark region (bottom-right corner) to preserve
image quality in the rest of the image.
"""

import asyncio
import logging
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import torch
from PIL import Image
from torchvision import transforms

from app.models.watermark_remover import WatermarkRemover

# Configure logging
logger = logging.getLogger(__name__)

# Model path - relative to backend folder
MODEL_PATH = Path(__file__).parent.parent.parent / "model.pth"

# Watermark region settings (Gemini logo is typically bottom-right)
WATERMARK_HEIGHT_RATIO = 0.15  # Process bottom 15% of image
WATERMARK_WIDTH_RATIO = 0.25   # Process right 25% of image
PATCH_SIZE = 256  # Model's native resolution


class WatermarkRemovalService:
    """
    Service for removing watermarks using a neural network model.
    
    Uses FODUU AI's trained model that achieves:
    - PSNR: 30.5 dB
    - SSIM: 0.92
    
    Strategy: Only processes the watermark region (bottom-right corner)
    to preserve quality in the rest of the image.
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize the watermark removal service.
        
        Args:
            model_path: Path to the model.pth file. Defaults to backend/model.pth
        """
        self.model_path = Path(model_path) if model_path else MODEL_PATH
        self.device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        self.model: Optional[WatermarkRemover] = None
        self._model_loaded = False
        
        # Transform for preprocessing (no resize - we'll handle regions)
        self.to_tensor = transforms.ToTensor()
        
        # Try to load model on init
        self._load_model()
    
    def _load_model(self) -> bool:
        """Load the watermark removal model."""
        if self._model_loaded:
            return True
        
        if not self.model_path.exists():
            logger.warning(f"⚠️ Watermark model not found at {self.model_path}")
            logger.warning("  Download from: https://huggingface.co/foduucom/Watermark_Removal")
            return False
        
        try:
            model = WatermarkRemover().to(self.device)
            model.load_state_dict(
                torch.load(self.model_path, map_location=self.device, weights_only=True)
            )
            model.eval()
            self.model = model
            self._model_loaded = True
            logger.info(f"✅ Watermark removal model loaded on {self.device}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load watermark model: {e}")
            return False
    
    @property
    def is_available(self) -> bool:
        """Check if the watermark removal service is available."""
        return self._model_loaded and self.model is not None
    
    async def remove_watermark(
        self,
        image_bytes: bytes,
        **kwargs,  # Accept but ignore legacy parameters for compatibility
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Remove watermark from an image using the neural network model.
        
        Args:
            image_bytes: Input image as bytes
            
        Returns:
            Tuple of (processed_image_bytes, error_message)
        """
        if not self.is_available:
            # Try to load model again
            if not self._load_model():
                logger.warning("Watermark model not available, returning original image")
                return image_bytes, None
        
        try:
            # Run inference in thread pool to avoid blocking
            result = await asyncio.to_thread(
                self._remove_watermark_sync,
                image_bytes,
            )
            return result
        except Exception as e:
            logger.error(f"Watermark removal error: {e}")
            return None, f"Watermark removal error: {str(e)}"
    
    def _remove_watermark_sync(
        self,
        image_bytes: bytes,
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Synchronous watermark removal - only processes watermark region.
        
        This preserves the original image quality by only modifying the
        bottom-right corner where the Gemini watermark typically appears.
        """
        if self.model is None:
            return None, "Model not loaded"
        
        try:
            # Load image
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            width, height = image.size
            
            # Calculate watermark region (bottom-right corner)
            wm_height = int(height * WATERMARK_HEIGHT_RATIO)
            wm_width = int(width * WATERMARK_WIDTH_RATIO)
            
            # Ensure minimum size for the model
            wm_height = max(wm_height, PATCH_SIZE)
            wm_width = max(wm_width, PATCH_SIZE)
            
            # Crop coordinates
            left = width - wm_width
            top = height - wm_height
            right = width
            bottom = height
            
            # Extract watermark region
            wm_region = image.crop((left, top, right, bottom))
            wm_region_size = wm_region.size
            
            # Resize region to model input size
            wm_region_resized = wm_region.resize((PATCH_SIZE, PATCH_SIZE), Image.Resampling.LANCZOS)
            
            # Process through model
            input_tensor = self.to_tensor(wm_region_resized).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                output_tensor = self.model(input_tensor)
            
            # Convert output to image
            output_array = (
                output_tensor.squeeze(0)
                .cpu()
                .permute(1, 2, 0)
                .clamp(0, 1)
                .numpy()
            )
            
            processed_region = Image.fromarray(
                (output_array * 255).astype(np.uint8)
            )
            
            # Resize back to original region size
            processed_region = processed_region.resize(
                wm_region_size, 
                Image.Resampling.LANCZOS
            )
            
            # Blend the processed region with original for smooth transition
            result_image = image.copy()
            
            # Create a gradient mask for smooth blending at edges
            blended_region = self._blend_regions(
                wm_region, 
                processed_region, 
                blend_margin=20
            )
            
            # Paste the processed region back
            result_image.paste(blended_region, (left, top))
            
            # Convert to bytes (PNG for lossless quality)
            buffer = BytesIO()
            result_image.save(buffer, format="PNG")
            
            return buffer.getvalue(), None
            
        except Exception as e:
            logger.error(f"Processing error: {e}")
            return None, f"Processing error: {str(e)}"
    
    def _blend_regions(
        self,
        original: Image.Image,
        processed: Image.Image,
        blend_margin: int = 20,
    ) -> Image.Image:
        """
        Blend processed region with original at the edges for smooth transition.
        
        Args:
            original: Original cropped region
            processed: Processed cropped region
            blend_margin: Pixels to blend at top and left edges
            
        Returns:
            Blended image
        """
        width, height = original.size
        
        # Create gradient mask (white in center/bottom-right, transparent at edges)
        mask = Image.new('L', (width, height), 255)
        mask_array = np.array(mask, dtype=np.float32)
        
        # Create gradient at top edge
        for y in range(min(blend_margin, height)):
            alpha = y / blend_margin
            mask_array[y, :] = int(255 * alpha)
        
        # Create gradient at left edge
        for x in range(min(blend_margin, width)):
            alpha = x / blend_margin
            mask_array[:, x] = np.minimum(mask_array[:, x], int(255 * alpha))
        
        mask = Image.fromarray(mask_array.astype(np.uint8), mode='L')
        
        # Composite: use processed where mask is white, original where transparent
        result = Image.composite(processed, original, mask)
        
        return result


# Singleton instance
_watermark_service: Optional[WatermarkRemovalService] = None


def get_watermark_service() -> WatermarkRemovalService:
    """Get or create the watermark removal service singleton."""
    global _watermark_service
    if _watermark_service is None:
        _watermark_service = WatermarkRemovalService()
    return _watermark_service
