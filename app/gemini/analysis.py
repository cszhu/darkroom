"""
Gemini API integration for image and video analysis.
"""

import logging
import re
from typing import Dict, List, Optional
from PIL import Image
from google.genai import types

from app.config import gemini_client
from app.image_processing.bounding_box import normalize_bounding_box
from app.utils.parsing import parse_gemini_json_response
from app.wikipedia.api import (
    fetch_multiple_wikipedia_pages,
    fetch_wikipedia_context,
    fetch_wikipedia_page,
    get_related_wikipedia_pages,
)

logger = logging.getLogger(__name__)


def extract_topics_from_metadata(metadata: Dict) -> List[str]:
    """Extract Wikipedia topics from metadata (capitalized phrases, historical events)."""
    text_fields = []
    
    # Collect text from all metadata fields
    for key in ["notes", "historical_context", "socioeconomic_inference", "lifestyle_insights"]:
        if metadata.get(key):
            text_fields.append(metadata[key])
    
    clothing = metadata.get("clothing_analysis")
    if isinstance(clothing, dict):
        text_fields.extend([clothing.get(k, "") for k in ["styles", "materials", "significance"] if clothing.get(k)])
    elif isinstance(clothing, str):
        text_fields.append(clothing)
    
    combined_text = " ".join(text_fields)
    topics = []
    
    # Extract capitalized phrases (2-4 words)
    capitalized_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b'
    matches = re.findall(capitalized_pattern, combined_text)
    
    skip_words = {"United States", "United Kingdom", "New York", "Los Angeles", "World War", "World War I", "World War II"}
    historical_keywords = ["war", "movement", "revolution", "period", "era", "decade", "navy", "army", "military", 
                         "regiment", "battalion", "act", "law", "treaty", "convention", "organization", "society", 
                         "association", "union", "dynasty", "empire", "kingdom", "republic"]
    
    for match in matches:
        if match in skip_words or re.match(r'^\d{4}', match):
            continue
        match_lower = match.lower()
        if (any(kw in match_lower for kw in historical_keywords) or len(match.split()) >= 2) and match not in topics:
            topics.append(match)
            if len(topics) >= 5:
                break
    
    # Extract patterns like "X War", "X Movement"
    pattern_matches = re.findall(r'\b([A-Z][a-z]+)\s+(War|Movement|Revolution|Act|Treaty|Convention)\b', combined_text)
    for match in pattern_matches:
        topic = " ".join(match)
        if topic not in topics:
            topics.append(topic)
            if len(topics) >= 5:
                break
    
    return topics[:5]


def build_analysis_prompt(width: int, height: int, location: Optional[str], user_context: Optional[str], wikipedia_context: Optional[str] = None) -> str:
    """
    Build the analysis prompt for Gemini.
    
    Args:
        width: Image width in pixels
        height: Image height in pixels
        location: Optional location where photo was taken
        user_context: Optional additional context from user
        wikipedia_context: Optional historical context from Wikipedia (already fetched)
        
    Returns:
        Formatted prompt string
    """
    historical_context_section = ""
    if wikipedia_context:
        historical_context_section = f"""

HISTORICAL CONTEXT (for reference):
{wikipedia_context}

Use this historical context to inform your analysis of the photo, especially regarding the era, location, and cultural context.
"""
    
    return f"""Analyze this image containing an old physical photograph.

BOUNDING BOX DETECTION:
Detect the complete rectangular boundaries of the physical photograph (all four edges: top, bottom, left, right).
- Include: photo paper edges, corners, white borders
- Exclude: cloth/fabric, table surfaces, shadows, background objects
- Capture the ENTIRE photo from edge to edge

ANALYSIS TASKS:
1. Bounding box coordinates (x, y, width, height) in pixels relative to {width}x{height}
2. Estimated year (single year or narrow range)
3. Clothing analysis: styles, materials, quality, significance
4. Socioeconomic inference from visual cues
5. Lifestyle insights
{f"6. How location ({location}) relates to the photo" if location else ""}
{historical_context_section}
{f"Location: {location}" if location else ""}
{f"User context: {user_context}" if user_context else ""}

Respond with ONLY valid JSON:
{{
    "bounding_box": {{"x": <int>, "y": <int>, "width": <int>, "height": <int>}},
    "metadata": {{
        "estimated_year": "<year or range>",
        "historical_context": "<narrative context - NO URLs>",
        "clothing_analysis": {{
            "styles": "<description>",
            "materials": "<materials>",
            "quality": "<assessment>",
            "significance": "<what clothing tells us>"
        }},
        "socioeconomic_inference": "<economic status inference>",
        "lifestyle_insights": "<lifestyle analysis>",
        "notes": "<detailed narrative combining visual + historical analysis>"
    }}
}}

Coordinates: x=left edge, y=top edge, width=left-to-right distance, height=top-to-bottom distance.
"""


def analyze_image(image_path: str, user_context: Optional[str] = None, location: Optional[str] = None) -> Dict:
    """
    Real Gemini API call for image analysis.
    Analyzes the image to detect the physical photograph and extract metadata.
    
    Args:
        image_path: Path to the uploaded image
        user_context: Optional additional context provided by user
        location: Optional location where photo was taken
        
    Returns:
        Dictionary with bounding_box and metadata
    """
    # Fallback to mock if Gemini is not available
    if not gemini_client:
        return fallback_mock_analysis(image_path, user_context)
    
    try:
        # Open image to get dimensions
        img = Image.open(image_path)
        width, height = img.size
        
        # Fetch Wikipedia context if location provided
        wikipedia_data = None
        related_pages = []
        
        if location:
            era_estimate = "mid-20th century"
            topics_to_fetch = get_related_wikipedia_pages(location, era_estimate)
            
            try:
                wikipedia_data = fetch_multiple_wikipedia_pages(location, era_estimate, topics_to_fetch or None)
                if wikipedia_data:
                    related_pages = wikipedia_data.get("related_pages", [])
            except Exception as e:
                logger.warning(f"Wikipedia fetch failed: {e}")
                wikipedia_data = None
            
            # Fallback to single location page
            if not related_pages:
                try:
                    single_page = fetch_wikipedia_context(location, era_estimate)
                    if single_page:
                        if not wikipedia_data:
                            wikipedia_data = {"combined_text": single_page.get("text", "")}
                        related_pages = [{"title": single_page.get("title", ""), "url": single_page.get("url", ""), "type": "location"}]
                except Exception as e:
                    logger.warning(f"Wikipedia fallback failed: {e}")
        
        # Build the prompt with Wikipedia context included
        wikipedia_context_text = wikipedia_data.get("combined_text", "") if wikipedia_data else None
        prompt = build_analysis_prompt(width, height, location, user_context, wikipedia_context_text)
        
        # Read image file
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()
        
        # Create chat and send analysis request
        chat = gemini_client.chats.create(
            model="gemini-2.0-flash",
            config=types.GenerateContentConfig(response_modalities=['TEXT'])
        )
        
        parts = [
            types.Part.from_bytes(data=image_data, mime_type="image/jpeg"),
            types.Part.from_text(text=prompt)
        ]
        response = chat.send_message(parts)
        
        # Extract text response
        response_text = ""
        for part in response.parts:
            if part.text:
                response_text += part.text
        
        # Parse JSON from response using utility function
        result = parse_gemini_json_response(response_text)
        
        # Validate and normalize bounding box using utility function
        bbox = result.get("bounding_box", {})
        bounding_box = normalize_bounding_box(bbox, width, height)
        
        metadata = result.get("metadata", {})
        
        # Backward compatibility: ensure estimated_year exists
        if "estimated_year" not in metadata:
            metadata["estimated_year"] = metadata.get("year", metadata.get("decade", "Unknown"))
        
        if user_context and "notes" in metadata:
            metadata["notes"] += f" User context: {user_context}"
        
        # Add Wikipedia links
        if related_pages:
            metadata["wikipedia_links"] = related_pages
        elif location:
            # Final fallback for location
            try:
                single_page = fetch_wikipedia_context(location, "mid-20th century")
                if single_page:
                    metadata["wikipedia_links"] = [{"title": single_page.get("title", ""), "url": single_page.get("url", ""), "type": "location"}]
            except Exception:
                pass
        else:
            # Auto-detect topics when no location provided
            try:
                extracted_topics = extract_topics_from_metadata(metadata)
                auto_links = []
                for topic in extracted_topics[:3]:
                    try:
                        topic_page = fetch_wikipedia_page(topic)
                        if topic_page:
                            auto_links.append({"title": topic_page["title"], "url": topic_page["url"], "type": "topic"})
                    except Exception:
                        continue
                if auto_links:
                    metadata["wikipedia_links"] = auto_links
            except Exception:
                pass
        
        return {
            "bounding_box": bounding_box,
            "metadata": metadata
        }
        
    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}", exc_info=True)
        return fallback_mock_analysis(image_path, user_context, location)


def analyze_video(video_path: str, user_context: Optional[str] = None, location: Optional[str] = None) -> Dict:
    """
    Analyze video using Gemini 3 Pro.
    Extracts historical metadata from video frames.
    
    Args:
        video_path: Path to the uploaded video file
        user_context: Optional additional context provided by user
        location: Optional location where video was taken
        
    Returns:
        Dictionary with metadata (no bounding_box for videos)
    """
    if not gemini_client:
        return fallback_mock_video_analysis(video_path, user_context)
    
    try:
        # Fetch Wikipedia context if location provided
        wikipedia_data = None
        related_pages = []
        
        if location:
            era_estimate = "mid-20th century"
            topics_to_fetch = get_related_wikipedia_pages(location, era_estimate)
            
            try:
                wikipedia_data = fetch_multiple_wikipedia_pages(location, era_estimate, topics_to_fetch or None)
                if wikipedia_data:
                    related_pages = wikipedia_data.get("related_pages", [])
            except Exception as e:
                print(f"Warning: Wikipedia fetch failed: {e}")
                wikipedia_data = None
            
            if not related_pages:
                try:
                    single_page = fetch_wikipedia_context(location, era_estimate)
                    if single_page:
                        if not wikipedia_data:
                            wikipedia_data = {"combined_text": single_page.get("text", "")}
                        related_pages = [{"title": single_page.get("title", ""), "url": single_page.get("url", ""), "type": "location"}]
                except Exception as e:
                    print(f"Warning: Wikipedia fallback failed: {e}")
        
        # Build video analysis prompt
        wikipedia_context_text = wikipedia_data.get("combined_text", "") if wikipedia_data else None
        historical_context_section = f"\n\nHISTORICAL CONTEXT:\n{wikipedia_context_text}\n" if wikipedia_context_text else ""
        
        prompt = f"""Analyze this historical video/film footage.

ANALYSIS TASKS:
1. Estimated year/era (single year or narrow range)
2. Historical context about the location and era
3. Clothing/styles visible in the video
4. Socioeconomic inference from visual cues
5. Lifestyle insights
6. Notable events, activities, or cultural elements
{f"7. How location ({location}) relates to what we see" if location else ""}
{historical_context_section}
{f"Location: {location}" if location else ""}
{f"User context: {user_context}" if user_context else ""}

Respond with ONLY valid JSON:
{{
    "metadata": {{
        "estimated_year": "<year or range>",
        "historical_context": "<narrative context - NO URLs>",
        "clothing_analysis": {{
            "styles": "<description>",
            "materials": "<materials>",
            "quality": "<assessment>",
            "significance": "<what clothing tells us>"
        }},
        "socioeconomic_inference": "<economic status inference>",
        "lifestyle_insights": "<lifestyle analysis>",
        "notes": "<detailed narrative combining visual + historical analysis>"
    }}
}}
"""
        
        # Read video file
        with open(video_path, "rb") as video_file:
            video_data = video_file.read()
        
        # Determine MIME type from file extension
        mime_type = "video/mp4"
        if video_path.endswith(".mov"):
            mime_type = "video/quicktime"
        elif video_path.endswith(".avi"):
            mime_type = "video/x-msvideo"
        elif video_path.endswith(".webm"):
            mime_type = "video/webm"
        
        # Use Gemini 3 Pro for video analysis
        # Create parts with video data
        parts = [
            types.Part.from_bytes(data=video_data, mime_type=mime_type),
            types.Part.from_text(text=prompt)
        ]
        
        response = gemini_client.models.generate_content(
            model="gemini-3-pro-preview",
            contents=parts
        )
        
        # Extract text response
        response_text = ""
        for part in response.parts:
            if part.text:
                response_text += part.text
        
        # Parse JSON from response
        result = parse_gemini_json_response(response_text)
        metadata = result.get("metadata", {})
        
        # Backward compatibility
        if "estimated_year" not in metadata:
            metadata["estimated_year"] = metadata.get("year", metadata.get("decade", "Unknown"))
        
        if user_context and "notes" in metadata:
            metadata["notes"] += f" User context: {user_context}"
        
        # Add Wikipedia links
        if related_pages:
            metadata["wikipedia_links"] = related_pages
        elif location:
            try:
                single_page = fetch_wikipedia_context(location, "mid-20th century")
                if single_page:
                    metadata["wikipedia_links"] = [{"title": single_page.get("title", ""), "url": single_page.get("url", ""), "type": "location"}]
            except Exception:
                pass
        else:
            # Auto-detect topics
            try:
                extracted_topics = extract_topics_from_metadata(metadata)
                auto_links = []
                for topic in extracted_topics[:3]:
                    try:
                        topic_page = fetch_wikipedia_page(topic)
                        if topic_page:
                            auto_links.append({"title": topic_page["title"], "url": topic_page["url"], "type": "topic"})
                    except Exception:
                        continue
                if auto_links:
                    metadata["wikipedia_links"] = auto_links
            except Exception:
                pass
        
        return {"metadata": metadata}
        
    except Exception as e:
        logger.error(f"Error analyzing video: {e}", exc_info=True)
        return fallback_mock_video_analysis(video_path, user_context, location)


def fallback_mock_video_analysis(video_path: str, user_context: Optional[str] = None, location: Optional[str] = None) -> Dict:
    """Fallback mock analysis for video if Gemini API fails"""
    notes = "Historical video footage detected. Appears to be vintage film."
    if user_context:
        notes += f" User provided context: {user_context}"
    
    metadata = {
        "estimated_year": "1950-1960",
        "decade": "1950s",
        "estimated_period": "Mid-20th century",
        "notes": notes,
        "user_context": user_context
    }
    
    return {"metadata": metadata}


def fallback_mock_analysis(image_path: str, user_context: Optional[str] = None, location: Optional[str] = None) -> Dict:
    """Fallback mock analysis if Gemini API fails"""
    img = Image.open(image_path)
    width, height = img.size
    
    margin_w = width * 0.1
    margin_h = height * 0.1
    
    bounding_box = {
        "x": int(margin_w),
        "y": int(margin_h),
        "width": int(width - 2 * margin_w),
        "height": int(height - 2 * margin_h)
    }
    
    notes = "Vintage photograph detected. Appears to be a family portrait."
    if user_context:
        notes += f" User provided context: {user_context}"
    
    metadata = {
        "year": "1980",
        "decade": "1980s",
        "estimated_period": "Late 20th century",
        "notes": notes,
        "user_context": user_context
    }
    
    return {
        "bounding_box": bounding_box,
        "metadata": metadata
    }

