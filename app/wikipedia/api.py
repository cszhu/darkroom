"""
Wikipedia API integration for fetching historical context.
FREE - no signup required.
"""

import requests
from typing import Dict, List, Optional


def fetch_wikipedia_page(page_title: str) -> Optional[Dict]:
    """
    Fetch a single Wikipedia page summary.
    
    Args:
        page_title: Wikipedia page title (e.g., "Shanghai", "Civil_Rights_Movement")
        
    Returns:
        Dictionary with 'extract' and 'url', or None if not found
    """
    headers = {'User-Agent': 'Darkroom Photo Restoration App'}
    
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{page_title.replace(' ', '_')}"
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            extract = data.get("extract", "")
            if extract:
                return {
                    "title": data.get("title", page_title),
                    "extract": extract,
                    "url": data.get("content_urls", {}).get("desktop", {}).get("page", "")
                }
    except Exception:
        pass
    
    return None


def fetch_wikipedia_context(location: str, era: str) -> Dict:
    """
    Fetch historical context from Wikipedia for a location.
    
    Returns dict with 'text', 'url', 'title' or None if not found.
    """
    # Clean location string - remove commas, extra spaces, and country suffixes
    cleaned_location = location.split(',')[0].strip()
    
    # Try multiple search terms to find relevant Wikipedia page
    search_terms = [cleaned_location, f"History of {cleaned_location}"]
    
    for term in search_terms:
        result = fetch_wikipedia_page(term)
        if result:
            context_with_era = f"Historical context for {cleaned_location} during {era}: {result['extract']}"
            return {
                "title": result["title"],
                "text": context_with_era[:1000],
                "url": result["url"]
            }
    
    return None


def get_related_wikipedia_pages(location: str, era: str) -> List[str]:
    """
    Find related Wikipedia pages based on location and era using OpenSearch API.
    Returns up to 3 relevant historical topic page titles.
    """
    headers = {'User-Agent': 'Darkroom Photo Restoration App'}
    cleaned_location = location.split(',')[0].strip()
    related_pages = []
    
    # Try multiple search strategies prioritizing historical content
    search_queries = [
        f"{cleaned_location} {era}",
        f"{era} {cleaned_location}",
        f"History of {cleaned_location}",
    ]
    
    # Use Wikipedia's search API (OpenSearch format)
    for query in search_queries:
        try:
            url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "opensearch",
                "search": query,
                "limit": 8,  # Get more results to filter better
                "format": "json"
            }
            response = requests.get(url, headers=headers, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if len(data) >= 2:
                    titles = data[1]
                    for title in titles:
                        # Filter out irrelevant pages
                        title_lower = title.lower()
                        cleaned_lower = cleaned_location.lower()
                        
                        # Skip if it's the location itself or disambiguation
                        if title_lower == cleaned_lower or "disambiguation" in title_lower:
                            continue
                        
                        # Skip Olympics, sports, and other non-historical pages
                        skip_keywords = ["olympics", "paralympics", "sport", "football", "basketball", 
                                       "baseball", "soccer", "championship", "tournament"]
                        if any(keyword in title_lower for keyword in skip_keywords):
                            continue
                        
                        # Prefer historically relevant pages
                        is_historical = (
                            "history" in title_lower or
                            era.lower() in title_lower or
                            cleaned_lower in title_lower or
                            any(keyword in title_lower for keyword in ["war", "movement", "revolution", "period", "era", "decade"])
                        )
                        
                        if title not in related_pages and is_historical:
                            related_pages.append(title)
                            if len(related_pages) >= 3:
                                break
        except Exception:
            continue
        
        if len(related_pages) >= 3:
            break
    
    return related_pages[:3]


def fetch_multiple_wikipedia_pages(location: str, era: str, topics: Optional[List[str]] = None) -> Dict:
    """
    Fetch multiple Wikipedia pages: location + optional topics.
    Returns dict with location, topics, combined_text, and related_pages.
    """
    result = {
        "location": None,
        "topics": [],
        "combined_text": "",
        "related_pages": []
    }
    
    # Fetch location page (always try to get this first)
    location_data = fetch_wikipedia_context(location, era)
    if not location_data:
        # If location page fetch failed, try just the cleaned location name
        cleaned_location = location.split(',')[0].strip()
        if cleaned_location != location:
            location_data = fetch_wikipedia_context(cleaned_location, era)
    
    if location_data:
        result["location"] = location_data
        result["related_pages"].append({
            "title": location_data["title"],
            "url": location_data["url"],
            "type": "location"
        })
        result["combined_text"] += location_data["text"] + "\n\n"
    
    # Fetch topic pages
    if topics:
        for topic in topics:
            topic_data = fetch_wikipedia_page(topic)
            if topic_data:
                result["topics"].append(topic_data)
                result["related_pages"].append({
                    "title": topic_data["title"],
                    "url": topic_data["url"],
                    "type": "topic"
                })
                topic_text = f"Context about {topic}: {topic_data['extract'][:500]}"
                result["combined_text"] += topic_text + "\n\n"
    
    # Trim combined text to reasonable length
    result["combined_text"] = result["combined_text"][:2000]
    
    return result

