# Multi-stage Dockerfile for ADAM UI + API

# Stage 1: Build Next.js application
FROM node:18-alpine AS frontend-builder

WORKDIR /app/ui

# Copy package files
COPY ui/package*.json ./
RUN npm ci

# Copy source files
COPY ui/ .

# Build Next.js static export
RUN npm run build
RUN npm run export || true  # export might not be needed with newer Next.js

# Stage 2: Python backend with static files
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy Python requirements and install
COPY requirements.txt* pyproject.toml* ./
RUN pip install --no-cache-dir fastapi uvicorn httpx google-cloud-aiplatform pydantic

# Copy the entire application
COPY . .

# Copy built static files from frontend
COPY --from=frontend-builder /app/ui/out ./static
# If using .next instead of out:
# COPY --from=frontend-builder /app/ui/.next/static ./static/_next/static
# COPY --from=frontend-builder /app/ui/public ./static

# Install the package if using pyproject.toml
RUN if [ -f pyproject.toml ]; then pip install -e .; fi

# Environment variables
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8080

# Run the server
CMD ["python", "-m", "uvicorn", "server.api:app", "--host", "0.0.0.0", "--port", "8080"]