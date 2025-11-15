FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for OpenCV
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Copy startup script
COPY start.sh .
RUN chmod +x start.sh

# Cloud Run will provide PORT environment variable
ENV PORT=8080

# Expose port
EXPOSE 8080

# Run the application using startup script
CMD ./start.sh

