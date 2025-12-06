"""
Image cropping utilities.
"""

from PIL import Image
from typing import Dict


def crop_image(image_path: str, bounding_box: Dict, output_path: str) -> str:
    """
    Crop image based on bounding box coordinates using Pillow.
    
    Args:
        image_path: Path to the original image
        bounding_box: Dictionary with x, y, width, height
        output_path: Path to save the cropped image
        
    Returns:
        Path to the cropped image
    """
    img = Image.open(image_path)
    original_width, original_height = img.size
    
    x = bounding_box["x"]
    y = bounding_box["y"]
    width = bounding_box["width"]
    height = bounding_box["height"]
    
    # Clamp to image bounds
    x = max(0, min(x, original_width))
    y = max(0, min(y, original_height))
    width = min(width, original_width - x)
    height = min(height, original_height - y)
    
    # Crop the image (left, top, right, bottom)
    cropped = img.crop((x, y, x + width, y + height))
    
    # Save cropped image
    cropped.save(output_path)
    
    return output_path

