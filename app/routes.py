"""
API routes for Darkroom app.
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.config import OUTPUTS_DIR, STATIC_DIR, UPLOADS_DIR
from app.gemini.analysis import analyze_image, analyze_video
from app.gemini.restoration import generate_video_from_image, restore_image
from app.image_processing.cropping import crop_image

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
async def root():
    """Serve the main HTML page"""
    return FileResponse(str(STATIC_DIR / "index.html"))


@router.post("/api/process")
async def process_image(
    file: UploadFile = File(...),
    location: Optional[str] = Form(None),
    historical_context: Optional[str] = Form(None),
    colorize: str = Form("true")
):
    """
    Process uploaded image or video: analyze and restore.
    
    Returns JSON with paths to processed files plus metadata.
    """
    try:
        # Validate file type
        is_video = file.content_type.startswith("video/")
        is_image = file.content_type.startswith("image/")
        
        if not (is_image or is_video):
            raise HTTPException(status_code=400, detail="File must be an image or video")
        
        # Save uploaded file
        upload_path = UPLOADS_DIR / file.filename
        with open(upload_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Parse colorize boolean
        should_colorize = colorize.lower() == "true"
        
        if is_video:
            # Analyze video with Gemini
            gemini_result = analyze_video(str(upload_path), historical_context, location)
            metadata = gemini_result["metadata"]
            
            # For videos, return metadata only (restoration would require frame extraction)
            return JSONResponse({
                "success": True,
                "type": "video",
                "original": f"/uploads/{file.filename}",
                "metadata": metadata
            })
        else:
            # Image processing (existing logic)
            gemini_result = analyze_image(str(upload_path), historical_context, location)
            bounding_box = gemini_result["bounding_box"]
            metadata = gemini_result["metadata"]
            
            # Crop image based on bounding box
            cropped_filename = f"cropped_{file.filename}"
            cropped_path = OUTPUTS_DIR / cropped_filename
            crop_image(str(upload_path), bounding_box, str(cropped_path))
            
            # Restore image with Gemini
            restored_filename = f"restored_{file.filename}"
            restored_path = OUTPUTS_DIR / restored_filename
            restore_image(str(cropped_path), metadata, str(restored_path), should_colorize)
            
            # Return results
            return JSONResponse({
                "success": True,
                "type": "image",
                "original": f"/uploads/{file.filename}",
                "cropped": f"/outputs/{cropped_filename}",
                "restored": f"/outputs/{restored_filename}",
                "metadata": metadata
            })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@router.get("/uploads/{filename}")
async def get_upload(filename: str):
    """Serve uploaded files"""
    file_path = UPLOADS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


@router.get("/outputs/{filename}")
async def get_output(filename: str):
    """Serve processed output files"""
    file_path = OUTPUTS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


@router.post("/api/generate-video")
async def generate_video_endpoint(
    restored_image_path: str = Form(...),
    metadata_json: str = Form(...)  # JSON string of metadata
):
    """
    Generate a video from a restored photo using Veo 3.1.
    Optional feature: brings restored photos to life with subtle motion.
    """
    try:
        # Parse metadata
        metadata_dict = json.loads(metadata_json)
        
        # Extract filename from path (could be relative or absolute)
        if restored_image_path.startswith("/outputs/"):
            # Relative path from API
            image_filename = restored_image_path.replace("/outputs/", "")
            restored_path = OUTPUTS_DIR / image_filename
        else:
            # Absolute path
            restored_path = Path(restored_image_path)
        
        if not restored_path.exists():
            raise HTTPException(status_code=404, detail="Restored image not found")
        
        # Generate video
        video_filename = f"video_{restored_path.stem}.mp4"
        video_path = OUTPUTS_DIR / video_filename
        
        result = generate_video_from_image(str(restored_path), metadata_dict, str(video_path))
        
        if result:
            return JSONResponse({
                "success": True,
                "video": f"/outputs/{video_filename}"
            })
        else:
            raise HTTPException(
                status_code=500, 
                detail="Video generation failed. Veo 3.1 may not be available in your API account or may require special access."
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Video generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Video generation error: {str(e)}")

