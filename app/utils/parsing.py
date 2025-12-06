"""
JSON parsing utilities for Gemini API responses.
"""

import json
import re
from typing import Dict


def parse_gemini_json_response(response_text: str) -> Dict:
    """
    Parse JSON from Gemini's text response.
    Handles markdown code blocks and other formatting.
    
    Args:
        response_text: Raw text response from Gemini
        
    Returns:
        Parsed JSON dictionary
        
    Raises:
        ValueError: If JSON cannot be parsed
    """
    # Try to extract JSON from markdown code blocks first
    json_match = re.search(r'\{[\s\S]*\}', response_text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    
    # Fallback: try to parse entire response
    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Could not parse JSON from Gemini response: {e}")

