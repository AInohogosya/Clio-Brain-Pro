#!/bin/bash
# Clio Brain Pro - Single Command Launch Script
# 
# This script starts the application with both Web UI and CLI interfaces.
# Usage: ./start.sh [--cli] [--port 8080]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default values
PORT=8080
MODE="server"
PYTHON=${PYTHON:-python3}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --cli|-c)
            MODE="cli"
            shift
            ;;
        --port|-p)
            PORT="$2"
            shift 2
            ;;
        --help|-h)
            echo -e "${CYAN}Clio Brain Pro - AI Organization Operating System${NC}"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --cli, -c          Start CLI interface instead of web server"
            echo "  --port, -p PORT    Set server port (default: 8080)"
            echo "  --help, -h         Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                 Start web server on port 8080"
            echo "  $0 --cli           Start CLI interface"
            echo "  $0 --port 3000     Start web server on port 3000"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${CYAN}"
echo "╔════════════════════════════════════════╗"
echo "║      CLIO BRAIN PRO - Starting...      ║"
echo "╚════════════════════════════════════════╝"
echo -e "${NC}"

# Check Python version
if ! command -v $PYTHON &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not found.${NC}"
    echo "Please install Python 3.8 or higher."
    exit 1
fi

PYTHON_VERSION=$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "${GREEN}✓${NC} Python version: ${PYTHON_VERSION}"

# Create necessary directories
mkdir -p data backups

# Initialize data directory if needed
if [ ! -f "data/organizations.json" ]; then
    echo -e "${YELLOW}⚡ Initializing data directory...${NC}"
    echo '{}' > data/organizations.json
    echo '{}' > data/missions.json
    echo '{}' > data/strategies.json
    echo '{}' > data/workstreams.json
    echo '{}' > data/tasks.json
    echo '{}' > data/episodes.json
    echo '{}' > data/actions.json
    echo '{}' > data/authority.json
    echo '{}' > data/credentials.json
    echo '{}' > data/treasury.json
    echo '{}' > data/planning.json
    echo '{}' > data/execution.json
    echo '{}' > data/reliability.json
    echo -e "${GREEN}✓${NC} Data files initialized"
fi

# Check for existing provider config
if [ -f "data/provider_config.json" ]; then
    PROVIDER=$(cat data/provider_config.json | grep -o '"provider"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
    MODEL=$(cat data/provider_config.json | grep -o '"model"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
    if [ -n "$PROVIDER" ]; then
        echo -e "${GREEN}✓${NC} Provider configured: ${PROVIDER} (${MODEL})"
    fi
else
    echo -e "${YELLOW}ℹ${NC} No provider configuration found. Use the UI or CLI to configure."
fi

echo ""

# Start the appropriate mode
case $MODE in
    cli)
        echo -e "${CYAN}Starting CLI interface...${NC}"
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        exec $PYTHON cli/clio_cli.py
        ;;
    server)
        echo -e "${CYAN}Starting web server...${NC}"
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        echo -e "  Web UI:   ${CYAN}http://localhost:${PORT}${NC}"
        echo -e "  API:      ${CYAN}http://localhost:${PORT}/api/${NC}"
        echo ""
        echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
        echo ""
        exec $PYTHON server.py --directory . --port $PORT 2>/dev/null || $PYTHON -c "
import sys
sys.path.insert(0, '.')
exec(open('server.py').read())
"
        ;;
esac
