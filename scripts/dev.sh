#!/bin/bash
# Development script to run both server and UI

set -e

echo "🚀 Starting ADAM Development Environment"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating Python virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
echo -e "${GREEN}Activating virtual environment...${NC}"
source venv/bin/activate

# Install/update Python dependencies
echo -e "${GREEN}Installing Python dependencies...${NC}"
pip install -q --upgrade pip
pip install -q fastapi uvicorn httpx pydantic
if [ -f "pyproject.toml" ]; then
    pip install -q -e .
fi

# Start the FastAPI server in background
echo -e "${GREEN}Starting FastAPI server on http://localhost:8000${NC}"
ENV=development python -m uvicorn server.api:app --host 0.0.0.0 --port 8000 --reload &
SERVER_PID=$!

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    kill $SERVER_PID 2>/dev/null || true
    if [ ! -z "$UI_PID" ]; then
        kill $UI_PID 2>/dev/null || true
    fi
    exit 0
}

trap cleanup INT TERM

# Wait for server to start
echo "Waiting for server to start..."
sleep 3

# Check if server is running
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo -e "${RED}Failed to start server!${NC}"
    kill $SERVER_PID 2>/dev/null || true
    exit 1
fi

# Install UI dependencies if needed
if [ ! -d "ui/node_modules" ]; then
    echo -e "${YELLOW}Installing UI dependencies...${NC}"
    cd ui
    npm install
    cd ..
fi

# Start the Next.js development server
echo -e "${GREEN}Starting Next.js UI on http://localhost:3000${NC}"
cd ui
npm run dev &
UI_PID=$!
cd ..

echo ""
echo "========================================"
echo -e "${GREEN}✅ Development environment is ready!${NC}"
echo ""
echo "🌐 UI:     http://localhost:3000"
echo "🔧 API:    http://localhost:8000"
echo "📊 Health: http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop all services"
echo "========================================"

# Wait for processes
wait