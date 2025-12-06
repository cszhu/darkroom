"""
API routes for Darkroom app.
"""

import shutil
from typing import Optional
from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from fastapi.responses import FileResponse, JSONResponse

from app.config import STATIC_DIR, UPLOADS_DIR, OUTPUTS_DIR
from app.gemini.analysis import analyze_image
from app.gemini.restoration import restore_image
from app.image_processing.cropping import crop_image

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
    Process uploaded image: analyze, crop, and restore.
    
    Returns JSON with paths to original, cropped, and restored images plus metadata.
    """
    try:
        # Validate file type
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Save uploaded file
        upload_path = UPLOADS_DIR / file.filename
        with open(upload_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Parse colorize boolean
        should_colorize = colorize.lower() == "true"
        
        # Analyze image with Gemini
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

