"""
Darkroom - Photo Restoration Web App
Backend API using FastAPI

Main entry point - creates FastAPI app and mounts routes.
"""

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import STATIC_DIR
from app.routes import router

# Initialize FastAPI app
app = FastAPI(title="Darkroom API", version="1.0.0")

# Mount static files directory
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include API routes
app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
