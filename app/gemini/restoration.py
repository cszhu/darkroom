"""
Gemini API integration for image restoration.
"""

from typing import Dict
from PIL import Image

from app.config import gemini_client


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
        print(f"Error restoring image: {e}")
        return fallback_mock_restoration(image_path, output_path, colorize)


def fallback_mock_restoration(image_path: str, output_path: str, colorize: bool = True) -> str:
    """Fallback mock restoration if Gemini API fails"""
    img = Image.open(image_path)
    
    if colorize:
        restored = img
    else:
        restored = img.convert("L")
    
    restored.save(output_path)
    return output_path

