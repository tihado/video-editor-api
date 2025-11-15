from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
import cv2
import requests
import tempfile
import os
from typing import Optional, List
import io
from PIL import Image
import subprocess
import shutil

app = FastAPI(title="Video Frame Extractor API")


class FrameRequest(BaseModel):
    video_url: str
    time: float  # Time in seconds


class VideoSection(BaseModel):
    section: int
    video_id: int  # Index in the video_urls list
    start_time: float  # Start time in seconds
    end_time: float  # Stop time in seconds


class ClipRequest(BaseModel):
    video_urls: List[str]  # List of video URLs
    video_parts: List[VideoSection]  # Array of sections to clip


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


def clip_and_merge_videos(video_urls: List[str], video_parts: List[VideoSection]) -> bytes:
    """Clip videos based on sections and merge them into one video."""
    downloaded_videos = []
    clip_files = []
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Download all videos
        for i, url in enumerate(video_urls):
            video_path = download_video(url)
            downloaded_videos.append(video_path)
        
        # Validate video indices
        for section in video_parts:
            if section.video_id < 0 or section.video_id >= len(video_urls):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid video_id {section.video_id} for section {section.section}"
                )
            if section.start_time < 0 or section.end_time <= section.start_time:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid time range for section {section.section}"
                )
        
        # Clip each section
        for section in video_parts:
            video_path = downloaded_videos[section.video_id]
            clip_path = os.path.join(temp_dir, f"clip_{section.section}.mp4")
            
            # Use ffmpeg to clip the video
            duration = section.end_time - section.start_time
            
            ffmpeg_cmd = [
                "ffmpeg",
                "-i", video_path,
                "-ss", str(section.start_time),
                "-t", str(duration),
                "-c", "copy",  # Copy codec for speed
                "-avoid_negative_ts", "make_zero",
                "-y",  # Overwrite output file
                clip_path
            ]
            
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to clip section {section.section}: {result.stderr}"
                )
            
            if not os.path.exists(clip_path):
                raise HTTPException(
                    status_code=500,
                    detail=f"Clip file not created for section {section.section}"
                )
            
            clip_files.append(clip_path)
        
        # Create file list for ffmpeg concat
        concat_file = os.path.join(temp_dir, "concat_list.txt")
        with open(concat_file, "w") as f:
            for clip_file in clip_files:
                f.write(f"file '{clip_file}'\n")
        
        # Merge all clips using ffmpeg concat
        output_path = os.path.join(temp_dir, "merged_video.mp4")
        
        merge_cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            "-y",
            output_path
        ]
        
        result = subprocess.run(
            merge_cmd,
            capture_output=True,
            text=True,
            timeout=600
        )
        
        if result.returncode != 0:
            # If copy codec fails, try re-encoding
            merge_cmd_reencode = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-c:v", "libx264",
                "-c:a", "aac",
                "-preset", "fast",
                "-y",
                output_path
            ]
            
            result = subprocess.run(
                merge_cmd_reencode,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            if result.returncode != 0:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to merge videos: {result.stderr}"
                )
        
        # Read the merged video
        if not os.path.exists(output_path):
            raise HTTPException(status_code=500, detail="Merged video file not created")
        
        with open(output_path, "rb") as f:
            video_bytes = f.read()
        
        return video_bytes
        
    finally:
        # Clean up all temporary files
        for video_path in downloaded_videos:
            if os.path.exists(video_path):
                os.unlink(video_path)
        
        for clip_file in clip_files:
            if os.path.exists(clip_file):
                os.unlink(clip_file)
        
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


@app.post("/clip-and-merge", response_class=Response)
async def clip_and_merge(request: ClipRequest):
    """
    Clip videos based on sections and merge them into one video.
    
    - **video_urls**: List of video URLs
    - **sections**: Array of sections with:
      - section: Unique identifier for the section
      - video_id: Index of the video in video_urls list (0-based)
      - start_time: Start time in seconds
      - end_time: Stop time in seconds
    
    Returns: Merged video file (MP4)
    """
    try:
        # Validate input
        if not request.video_urls:
            raise HTTPException(status_code=400, detail="video_urls cannot be empty")
        
        if not request.video_parts:
            raise HTTPException(status_code=400, detail="video_parts cannot be empty")
        
        # Clip and merge videos
        video_bytes = clip_and_merge_videos(request.video_urls, request.video_parts)
        
        return Response(
            content=video_bytes,
            media_type="video/mp4",
            headers={"Content-Disposition": "attachment; filename=merged_video.mp4"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/")
async def root():
    return {
        "message": "Video Frame Extractor API",
        "endpoints": {
            "POST /extract-frame": "Extract a frame from a video URL at a specific time",
            "POST /clip-and-merge": "Clip videos based on sections and merge into one video"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint for Cloud Run"""
    return {"status": "healthy"}

