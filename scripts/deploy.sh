#!/bin/bash
# Deploy script for Google Cloud Run

set -e

echo "🚀 Deploying ADAM to Google Cloud Run"
echo "======================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check for required environment variables or use defaults
PROJECT_ID=${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}
REGION=${GCP_REGION:-"us-central1"}
SERVICE_NAME=${SERVICE_NAME:-"adam-ui"}
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: GCP_PROJECT_ID is not set and no default project found${NC}"
    echo "Please set GCP_PROJECT_ID or configure gcloud default project"
    exit 1
fi

echo "Configuration:"
echo "  Project ID: $PROJECT_ID"
echo "  Region: $REGION"
echo "  Service: $SERVICE_NAME"
echo "  Image: $IMAGE_NAME"
echo ""

# Enable required APIs
echo -e "${YELLOW}Enabling required GCP APIs...${NC}"
gcloud services enable cloudbuild.googleapis.com run.googleapis.com --project $PROJECT_ID

# Build and push the container
echo -e "${GREEN}Building container image...${NC}"
gcloud builds submit \
    --tag $IMAGE_NAME \
    --project $PROJECT_ID \
    --timeout=20m

# Deploy to Cloud Run
echo -e "${GREEN}Deploying to Cloud Run...${NC}"
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME \
    --platform managed \
    --region $REGION \
    --project $PROJECT_ID \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --min-instances 0 \
    --max-instances 10 \
    --port 8080 \
    --set-env-vars "ENV=production"

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
    --platform managed \
    --region $REGION \
    --project $PROJECT_ID \
    --format 'value(status.url)')

echo ""
echo "======================================"
echo -e "${GREEN}✅ Deployment successful!${NC}"
echo ""
echo "🌐 Service URL: $SERVICE_URL"
echo ""
echo "Test your deployment:"
echo "  curl ${SERVICE_URL}/health"
echo ""
echo "View logs:"
echo "  gcloud run logs read --service=$SERVICE_NAME --region=$REGION"
echo "======================================"