# Video Frame Extractor API

A Python API that extracts a frame from a video at a specific time.

## Installation

```bash
pip install -r requirements.txt
```

## Running the API

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

## API Endpoints

### POST /extract-frame

Extract a frame from a video URL at a specific time.

**Request Body:**
```json
{
  "video_url": "https://example.com/video.mp4",
  "time": 5.5
}
```

**Parameters:**
- `video_url` (string): URL of the video file
- `time` (float): Time in seconds (e.g., 5.5 for 5.5 seconds)

**Response:**
- Returns a PNG image of the frame at the specified time

**Example using curl:**
```bash
curl -X POST "http://localhost:8000/extract-frame" \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://example.com/video.mp4", "time": 5.5}' \
  --output frame.png
```

**Example using Python:**
```python
import requests

response = requests.post(
    "http://localhost:8000/extract-frame",
    json={
        "video_url": "https://example.com/video.mp4",
        "time": 5.5
    }
)

with open("frame.png", "wb") as f:
    f.write(response.content)
```

## API Documentation

Once the server is running, you can access:
- Interactive API docs: `http://localhost:8000/docs`
- Alternative docs: `http://localhost:8000/redoc`

## Deployment to Google Cloud Run

### Prerequisites

1. Install [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
2. Install [Docker](https://docs.docker.com/get-docker/)
3. Authenticate with Google Cloud:
   ```bash
   gcloud auth login
   gcloud auth configure-docker
   ```

### Option 1: Deploy using the deployment script

1. Set your Google Cloud project ID:
   ```bash
   export GOOGLE_CLOUD_PROJECT="your-project-id"
   ```

2. Make the script executable and run it:
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

### Option 2: Deploy using Cloud Build

1. Set your Google Cloud project ID:
   ```bash
   export GOOGLE_CLOUD_PROJECT="your-project-id"
   ```

2. Make the script executable and run it:
   ```bash
   chmod +x deploy-cloud-build.sh
   ./deploy-cloud-build.sh
   ```

### Option 3: Manual deployment

1. Build and push the Docker image:
   ```bash
   export PROJECT_ID="your-project-id"
   docker build -t gcr.io/${PROJECT_ID}/video-frame-extractor:latest .
   docker push gcr.io/${PROJECT_ID}/video-frame-extractor:latest
   ```

2. Deploy to Cloud Run:
   ```bash
   gcloud run deploy video-frame-extractor \
     --image gcr.io/${PROJECT_ID}/video-frame-extractor:latest \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --memory 2Gi \
     --cpu 2 \
     --timeout 300
   ```

### Configuration

The deployment uses:
- **Memory**: 2GB (adjustable for larger videos)
- **CPU**: 2 cores
- **Timeout**: 300 seconds (5 minutes)
- **Region**: us-central1 (changeable)

After deployment, you'll receive a URL like:
`https://video-frame-extractor-xxxxx-uc.a.run.app`

You can then use this URL instead of `localhost:8000` in your API calls.

