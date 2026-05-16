# Async Image Processing in FastAPI: Complete Guide

## Overview

This document explains how to handle CPU-bound image processing operations in async Python web applications, specifically focusing on profile picture uploads.

## Original Synchronous Code

```python
import uuid
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageOps

PROFILE_PICS_DIR = Path("media/profile_pics")

def process_profile_image(content: bytes) -> str:
    """Process and save profile picture, return filename"""
    with Image.open(BytesIO(content)) as original:
        # Fix orientation from camera metadata
        img = ImageOps.exif_transpose(original)
        
        # Resize and crop to exact 300x300 pixels
        img = ImageOps.fit(img, (300, 300), method=Image.Resampling.LANCZOS)
        
        # Convert to RGB (remove alpha channel if present)
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        
        # Generate unique filename
        filename = f"{uuid.uuid4().hex}.jpg"
        filepath = PROFILE_PICS_DIR / filename
        
        # Ensure directory exists
        PROFILE_PICS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Save as optimized JPEG
        img.save(filepath, "JPEG", quality=85, optimize=True)
    
    return filename

# In an async route (FastAPI, aiohttp, Sanic, etc.)
@app.post("/upload")
async def upload_profile_pic(file: bytes):
    # ❌ PROBLEM: This blocks the entire event loop!
    filename = process_profile_image(file)  # Takes 50-200ms
    return {"filename": filename}

Your async routes share a single event loop (typically 1 thread)
When process_profile_image() runs, it blocks the loop completely
No other requests can be processed during that 50-200ms
With multiple concurrent uploads, everything queues up → severe latency

Understanding Blocking Operations
CPU-Bound Operations (Image processing):
Resizing (mathematical calculations on every pixel)
Color conversion (RGB transformation)
JPEG compression (complex algorithms)
These hold the GIL - even threads don't help much

I/O-Bound Operations (File system):
Creating directories (mkdir)
Writing files (img.save())
These block the event loop but can be moved to threads


# Without thread pool:
# Request 1: |====50ms====|
# Request 2:                |====50ms====|
# Request 3:                               |====50ms====|
# Total time for 3 requests: 150ms

# With thread pool (4 workers):
# Request 1: |====50ms====|
# Request 2: |====50ms====|
# Request 3: |====50ms====|
# Request 4: |====50ms====|
# Total time for 3 requests: ~50ms