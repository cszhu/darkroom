"""
Gemini API integration for image restoration and video generation.
"""

import io
import logging
import time
from typing import Dict, Optional
from PIL import Image
from google.genai import types

from app.config import gemini_client

logger = logging.getLogger(__name__)


def restore_image(image_path: str, metadata: Dict, output_path: str, colorize: bool = True) -> str:
    """
    Restore and enhance vintage photograph using Gemini image generation.
    
    Args:
        image_path: Path to the cropped image
        metadata: Historical metadata from Gemini analysis
        output_path: Path to save the restored image
        colorize: Whether to colorize the image
        
    Returns:
        Path to the restored image
    """
    if not gemini_client:
        return fallback_mock_restoration(image_path, output_path, colorize)
    
    try:
        year_info = metadata.get("estimated_year", metadata.get("year", metadata.get("decade", "")))
        period_info = metadata.get("estimated_period", "")
        notes = metadata.get("notes", "")
        
        colorize_instruction = "Colorize this black and white photograph with historically accurate colors." if colorize else "Keep the original color scheme."
        
        prompt = f"""Restore and enhance this vintage photograph from {year_info} ({period_info}).

{colorize_instruction}

RESTORATION:
- Remove scratches, dust, damage, fading, discoloration
- Enhance clarity, sharpness, and missing details
- Maintain historical authenticity

EXTENSION (CONSERVATIVE):
- Only extend elements already partially visible
- Continue visible patterns/textures/structures
- Keep historically accurate for {period_info}

CRITICAL - PRESERVE BACKGROUNDS:
- Keep white/blank/empty backgrounds exactly as they appear
- Do NOT add new objects or scenes to empty areas
- Preserve original composition, poses, expressions

{"Context: " + notes if notes else ""}

Output: Complete restored version with damage repaired. Extend only partially visible elements. Preserve white/blank backgrounds.
"""
        
        img = Image.open(image_path)
        response = gemini_client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=[prompt, img]
        )
        
        # Extract image from response
        for part in response.parts:
            if part.inline_data is not None:
                restored_image = part.as_image()
                restored_image.save(output_path)
                return output_path
        
        # Fallback if no image returned
        return fallback_mock_restoration(image_path, output_path, colorize)
            
    except Exception as e:
        logger.error(f"Error restoring image: {e}", exc_info=True)
        return fallback_mock_restoration(image_path, output_path, colorize)


def generate_video_from_image(image_path: str, metadata: Dict, output_path: str) -> Optional[str]:
    """
    Generate a short 3-4 second video from a restored photo using Veo 3.1.
    Uses the image as a reference to guide video generation.
    
    Args:
        image_path: Path to the restored image
        metadata: Historical metadata
        output_path: Path to save the generated video
        
    Returns:
        Path to the generated video, or None if generation fails
    """
    if not gemini_client:
        return None
    
    try:
        year_info = metadata.get("estimated_year", metadata.get("year", metadata.get("decade", "")))
        period_info = metadata.get("estimated_period", "")
        notes = metadata.get("notes", "")
        
        # Build prompt for 3-4 second video generation
        prompt = f"""Bring this historical photograph from {year_info} ({period_info}) to life as a short cinematic video.

ANIMATION REQUIREMENTS:
- Animate the PEOPLE and SUBJECTS in the scene - they should move naturally
- Subtle, realistic motion: gentle breathing, slight head movements, natural gestures
- People should appear alive and present, not frozen
- If there are multiple people, show natural interaction between them
- Animate any visible elements: clothing movement, hair swaying, natural body language

CAMERA:
- Very subtle camera movement only - the focus should be on the subjects moving
- Avoid excessive zooming or panning
- Keep the composition similar to the original photograph

STYLE:
- Cinematic, respectful, historically accurate
- Preserve the original mood and atmosphere
- Period-appropriate movement and behavior
- Natural lighting and shadows that move subtly

{"Context: " + notes[:200] if notes else ""}

IMPORTANT: The people in the photograph must move and come to life. Do not just zoom or pan the camera - animate the subjects themselves."""
        
        # Read image and check aspect ratio
        # Veo requires 16:9 aspect ratio, so we'll pad vertical images to preserve proportions
        img = Image.open(image_path)
        original_width, original_height = img.size
        original_aspect = original_width / original_height
        
        # Determine MIME type
        mime_type = "image/jpeg"
        if image_path.lower().endswith(('.png',)):
            mime_type = "image/png"
        
        # If image is vertical (portrait), pad it to 16:9 to avoid stretching
        # Target aspect ratio is 16:9 = 1.777...
        target_aspect = 16 / 9
        
        if original_aspect < target_aspect:
            # Vertical image - pad horizontally to 16:9
            target_width = int(original_height * target_aspect)
            padded_img = Image.new('RGB', (target_width, original_height), color='black')
            # Center the original image
            x_offset = (target_width - original_width) // 2
            padded_img.paste(img, (x_offset, 0))
            img = padded_img
            logger.debug(f"Padded vertical image from {original_width}x{original_height} to {target_width}x{original_height} to preserve aspect ratio")
        elif original_aspect > target_aspect:
            # Horizontal image wider than 16:9 - pad vertically
            target_height = int(original_width / target_aspect)
            padded_img = Image.new('RGB', (original_width, target_height), color='black')
            # Center the original image
            y_offset = (target_height - original_height) // 2
            padded_img.paste(img, (0, y_offset))
            img = padded_img
            logger.debug(f"Padded horizontal image from {original_width}x{original_height} to {original_width}x{target_height} to preserve aspect ratio")
        
        # Convert PIL image to bytes
        img_bytes_io = io.BytesIO()
        img.save(img_bytes_io, format='JPEG' if mime_type == 'image/jpeg' else 'PNG', quality=95)
        image_bytes = img_bytes_io.getvalue()
        
        # Create Image object with inline bytes
        # The SDK will handle base64 encoding internally for the API
        image_obj = types.Image(
            imageBytes=image_bytes,
            mimeType=mime_type
        )
        
        # Use Veo 3.1 with image as reference
        reference_image = types.VideoGenerationReferenceImage(
            image=image_obj,
            reference_type="asset"
        )
        
        # Generate video using Veo API
        # Note: durationSeconds must be "8" when using referenceImages (per API docs)
        # aspectRatio must be "16:9" when using referenceImages
        # Note: generateAudio parameter is not supported in Gemini API, so we rely on prompt instructions
        operation = gemini_client.models.generate_videos(
            model="veo-3.1-generate-preview",
            prompt=prompt,
            config=types.GenerateVideosConfig(
                reference_images=[reference_image],
                duration_seconds="8",  # Required: must be "8" when using referenceImages
                aspect_ratio="16:9",  # Required: only supports 16:9 with referenceImages
            ),
        )
        
        # Poll the operation status until the video is ready
        max_wait_time = 300  # 5 minutes max
        wait_time = 0
        while not operation.done and wait_time < max_wait_time:
            logger.info(f"Waiting for video generation... ({wait_time}s)")
            time.sleep(10)
            wait_time += 10
            try:
                operation = gemini_client.operations.get(operation)
            except Exception as e:
                logger.error(f"Error polling operation: {e}", exc_info=True)
                raise
        
        if not operation.done:
            logger.warning("Video generation timed out")
            return None
        
        # Check for errors in operation
        if hasattr(operation, 'error') and operation.error:
            error_msg = f"Operation error: {operation.error}"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        # Download the video
        if not operation.response:
            logger.warning("Operation completed but no response found")
            return None
        
        # Check for RAI (Responsible AI) safety filters
        rai_count = getattr(operation.response, 'rai_media_filtered_count', None)
        if rai_count is not None and rai_count > 0:
            reasons = getattr(operation.response, 'rai_media_filtered_reasons', [])
            reason_msg = "; ".join(reasons) if reasons else "Content was filtered by safety filters"
            logger.warning(f"Video generation blocked by safety filters: {reason_msg}")
            raise Exception(f"Video generation was blocked: {reason_msg}")
        
        if not hasattr(operation.response, 'generated_videos') or not operation.response.generated_videos:
            logger.warning(f"Operation completed but no videos generated. Response: {operation.response}")
            raise Exception("Video generation completed but no video was produced. This may be due to content safety filters or API limitations.")
        
        video = operation.response.generated_videos[0]
        if not hasattr(video, 'video') or not video.video:
            raise Exception("Video object missing video file reference")
        
        try:
            gemini_client.files.download(file=video.video)
            video.video.save(output_path)
            logger.info(f"Generated video saved to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error downloading/saving video: {e}", exc_info=True)
            raise
        
    except AttributeError as e:
        logger.warning(f"Veo API not available - AttributeError: {e}")
        logger.warning("Note: Veo 3.1 may require special API access or different SDK version")
        return None
    except Exception as e:
        logger.error(f"Error generating video: {e}", exc_info=True)
        return None


def fallback_mock_restoration(image_path: str, output_path: str, colorize: bool = True) -> str:
    """Fallback mock restoration if Gemini API fails"""
    img = Image.open(image_path)
    
    if colorize:
        restored = img
    else:
        restored = img.convert("L")
    
    restored.save(output_path)
    return output_path

