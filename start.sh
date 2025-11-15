#!/bin/bash
# Startup script for Cloud Run - reads PORT from environment variable

PORT=${PORT:-8080}
uvicorn main:app --host 0.0.0.0 --port $PORT

