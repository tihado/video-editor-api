from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
import cv2
import requests
import tempfile
import os
from typing import Optional
import io
from PIL import Image

app = FastAPI(title="Video Frame Extractor API")


class FrameRequest(BaseModel):
    video_url: str
    time: float  # Time in seconds


def download_video(url: str) -> str:
    """Download video from URL to a temporary file."""
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        for chunk in response.iter_content(chunk_size=8192):
            temp_file.write(chunk)
        temp_file.close()
        
        return temp_file.name
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to download video: {str(e)}")


def extract_frame(video_path: str, time_seconds: float) -> bytes:
    """Extract a frame from video at the specified time."""
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail="Failed to open video file")
    
    # Get video FPS and total frames
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    
    # Validate time
    if time_seconds < 0:
        raise HTTPException(status_code=400, detail="Time must be non-negative")
    
    if duration > 0 and time_seconds > duration:
        raise HTTPException(status_code=400, detail=f"Time {time_seconds}s exceeds video duration {duration:.2f}s")
    
    # Calculate frame number
    frame_number = int(time_seconds * fps)
    
    # Set video position to the desired frame
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    
    # Read the frame
    ret, frame = cap.read()
    cap.release()
    
    if not ret or frame is None:
        raise HTTPException(status_code=400, detail="Failed to extract frame from video")
    
    # Convert BGR to RGB (OpenCV uses BGR, PIL uses RGB)
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # Convert to PIL Image and then to bytes
    img = Image.fromarray(frame_rgb)
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    return img_byte_arr.getvalue()


@app.post("/extract-frame", response_class=Response)
async def extract_frame_from_video(request: FrameRequest):
    """
    Extract a frame from a video at a specific time.
    
    - **video_url**: URL of the video file
    - **time**: Time in seconds (e.g., 5.5 for 5.5 seconds)
    
    Returns: PNG image of the frame
    """
    video_path = None
    try:
        # Download video
        video_path = download_video(request.video_url)
        
        # Extract frame
        image_bytes = extract_frame(video_path, request.time)
        
        return Response(
            content=image_bytes,
            media_type="image/png",
            headers={"Content-Disposition": "attachment; filename=frame.png"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        # Clean up temporary file
        if video_path and os.path.exists(video_path):
            os.unlink(video_path)


@app.get("/")
async def root():
    return {
        "message": "Video Frame Extractor API",
        "endpoints": {
            "POST /extract-frame": "Extract a frame from a video URL at a specific time"
        }
    }

