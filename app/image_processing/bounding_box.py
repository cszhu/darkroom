"""
Bounding box normalization and validation utilities.
"""

from typing import Dict


def normalize_bounding_box(bbox: Dict, image_width: int, image_height: int) -> Dict:
    """
    Normalize and validate bounding box coordinates.
    
    Args:
        bbox: Raw bounding box dict from Gemini
        image_width: Image width in pixels
        image_height: Image height in pixels
        
    Returns:
        Normalized bounding box dict
    """
    # Parse bounding box values
    x = int(bbox.get("x", image_width * 0.1))
    y = int(bbox.get("y", image_height * 0.1))
    bbox_width = int(bbox.get("width", image_width * 0.8))
    bbox_height = int(bbox.get("height", image_height * 0.8))
    
    # Clamp to image bounds
    x = max(0, min(x, image_width - 1))
    y = max(0, min(y, image_height - 1))
    bbox_width = max(1, min(bbox_width, image_width - x))
    bbox_height = max(1, min(bbox_height, image_height - y))
    
    # Warn if coverage is low
    width_coverage = bbox_width / image_width
    height_coverage = bbox_height / image_height
    if width_coverage < 0.90 or height_coverage < 0.90:
        print(f"Warning: Low bounding box coverage ({width_coverage*100:.1f}% width, {height_coverage*100:.1f}% height)")
    
    return {
        "x": x,
        "y": y,
        "width": bbox_width,
        "height": bbox_height
    }

