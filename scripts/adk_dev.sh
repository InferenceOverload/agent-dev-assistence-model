#!/bin/bash
# Development script for running ADK with custom UI

set -e

echo "🚀 ADAM Agent Development with ADK"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse command line arguments
MODE=${1:-"custom"}  # custom, adk-web, adk-api

case $MODE in
    "adk-web")
        echo -e "${GREEN}Starting ADK Web UI...${NC}"
        echo "This provides Google's built-in development UI"
        echo ""
        echo "Opening at: http://localhost:8000"
        echo "Features: Tool inspection, voice chat, event tracing"
        echo ""
        adk web
        ;;
        
    "adk-api")
        echo -e "${GREEN}Starting ADK API Server...${NC}"
        echo "This provides REST API endpoints for your agent"
        echo ""
        echo "API will be available at: http://localhost:8080"
        echo ""
        echo "Test with:"
        echo "  curl -X POST http://localhost:8080/agent/run \\"
        echo "    -H 'Content-Type: application/json' \\"
        echo "    -d '{\"input\": \"Hello\"}'"
        echo ""
        adk api_server
        ;;
        
    "custom")
        echo -e "${GREEN}Starting Custom UI with FastAPI Bridge...${NC}"
        echo ""
        
        # Check if virtual environment exists
        if [ ! -d "venv" ]; then
            echo -e "${YELLOW}Creating Python virtual environment...${NC}"
            python3 -m venv venv
        fi
        
        # Activate virtual environment
        source venv/bin/activate
        
        # Install Python dependencies
        echo -e "${YELLOW}Installing Python dependencies...${NC}"
        pip install -q --upgrade pip
        pip install -q fastapi uvicorn httpx pydantic google-generativeai
        
        # Install the package
        if [ -f "pyproject.toml" ]; then
            pip install -q -e .
        fi
        
        # Start FastAPI server
        echo -e "${GREEN}Starting FastAPI bridge server...${NC}"
        python -m uvicorn server.api:app --host 0.0.0.0 --port 8000 --reload &
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
        
        # Start Next.js UI
        echo -e "${GREEN}Starting Next.js UI...${NC}"
        cd ui
        npm run dev &
        UI_PID=$!
        cd ..
        
        echo ""
        echo "=================================="
        echo -e "${GREEN}✅ Custom UI is ready!${NC}"
        echo ""
        echo "🌐 UI:     http://localhost:3000"
        echo "🔧 API:    http://localhost:8000"
        echo "📊 Health: http://localhost:8000/health"
        echo ""
        echo -e "${BLUE}Note:${NC} The server will try to:"
        echo "  1. Use agent.run_async() if available"
        echo "  2. Fall back to direct tool calls if needed"
        echo "  3. Proxy to ADK API server if running on :8080"
        echo ""
        echo "Press Ctrl+C to stop all services"
        echo "=================================="
        
        # Wait for processes
        wait
        ;;
        
    "both")
        echo -e "${GREEN}Starting BOTH ADK API Server and Custom UI...${NC}"
        echo ""
        
        # Start ADK API server in background
        echo -e "${YELLOW}Starting ADK API Server on :8080...${NC}"
        adk api_server &
        ADK_PID=$!
        
        sleep 3
        
        # Start custom UI (it will proxy to ADK API)
        echo -e "${YELLOW}Starting Custom UI on :3000...${NC}"
        $0 custom &
        CUSTOM_PID=$!
        
        # Cleanup function
        cleanup() {
            echo -e "\n${YELLOW}Shutting down all services...${NC}"
            kill $ADK_PID 2>/dev/null || true
            kill $CUSTOM_PID 2>/dev/null || true
            exit 0
        }
        
        trap cleanup INT TERM
        
        echo ""
        echo "=================================="
        echo -e "${GREEN}✅ Both servers are running!${NC}"
        echo ""
        echo "🤖 ADK API: http://localhost:8080 (Google's API)"
        echo "🌐 Custom:  http://localhost:3000 (Your UI)"
        echo ""
        echo "The custom UI will proxy to ADK API when available"
        echo "=================================="
        
        wait
        ;;
        
    *)
        echo -e "${RED}Unknown mode: $MODE${NC}"
        echo ""
        echo "Usage: $0 [mode]"
        echo ""
        echo "Modes:"
        echo "  adk-web   - Run Google's ADK Web UI (built-in)"
        echo "  adk-api   - Run ADK API Server only"
        echo "  custom    - Run custom FastAPI + Next.js UI"
        echo "  both      - Run ADK API + Custom UI together"
        echo ""
        echo "Examples:"
        echo "  $0 adk-web    # Use Google's UI"
        echo "  $0 custom     # Use your custom UI"
        echo "  $0 both       # Run both for comparison"
        exit 1
        ;;
esac