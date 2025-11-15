#!/bin/bash

# Deploy using Google Cloud Build

set -e

PROJECT_ID=${GOOGLE_CLOUD_PROJECT:-"your-project-id"}

echo "Deploying using Cloud Build..."
echo "Project ID: ${PROJECT_ID}"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "Error: gcloud CLI is not installed. Please install it from https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Set the project
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo "Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Submit build to Cloud Build
echo "Submitting build to Cloud Build..."
gcloud builds submit --config cloudbuild.yaml .

echo ""
echo "✅ Deployment complete!"
echo "Check your Cloud Run service in the Google Cloud Console"

