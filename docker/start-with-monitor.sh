#!/bin/bash
# ============================================================================
# Docker Compose Startup Script with Process Monitor
# ============================================================================
# This script starts all TradingAgents-CN services with optional monitoring
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.yml"
ENABLE_MONITOR=${ENABLE_MONITOR:-false}
ENABLE_MANAGEMENT=${ENABLE_MANAGEMENT:-false}

echo -e "${CYAN}============================================================================${NC}"
echo -e "${CYAN}  TradingAgents-CN Docker Startup${NC}"
echo -e "${CYAN}============================================================================${NC}"
echo ""

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}ERROR: docker-compose is not installed${NC}"
    exit 1
fi

# Create necessary directories
echo -e "${YELLOW}Creating necessary directories...${NC}"
mkdir -p logs data config runtime

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}WARNING: .env file not found${NC}"
    if [ -f .env.docker ]; then
        echo -e "${YELLOW}Copying .env.docker to .env...${NC}"
        cp .env.docker .env
    else
        echo -e "${RED}ERROR: Neither .env nor .env.docker found${NC}"
        exit 1
    fi
fi

# Build profile arguments
PROFILE_ARGS=""
if [ "$ENABLE_MANAGEMENT" = "true" ]; then
    PROFILE_ARGS="--profile management"
    echo -e "${GREEN}Management tools enabled (Redis Commander, Mongo Express)${NC}"
fi

# Stop any existing containers
echo ""
echo -e "${YELLOW}Stopping existing containers...${NC}"
docker-compose down

# Start services
echo ""
echo -e "${YELLOW}Starting services...${NC}"
docker-compose up -d $PROFILE_ARGS

# Wait for services to be healthy
echo ""
echo -e "${YELLOW}Waiting for services to be healthy...${NC}"
sleep 10

# Check service status
echo ""
echo -e "${CYAN}Service Status:${NC}"
docker-compose ps

# Show logs
echo ""
echo -e "${CYAN}Recent logs:${NC}"
docker-compose logs --tail=20

echo ""
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}  All Services Started Successfully!${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo ""
echo -e "${CYAN}Service URLs:${NC}"
echo -e "  Backend API:  ${GREEN}http://localhost:8000${NC}"
echo -e "  Frontend:     ${GREEN}http://localhost:3000${NC}"
echo -e "  MongoDB:      ${GREEN}mongodb://localhost:27017${NC}"
echo -e "  Redis:        ${GREEN}redis://localhost:6379${NC}"

if [ "$ENABLE_MANAGEMENT" = "true" ]; then
    echo ""
    echo -e "${CYAN}Management Tools:${NC}"
    echo -e "  Redis Commander:  ${GREEN}http://localhost:8081${NC}"
    echo -e "  Mongo Express:    ${GREEN}http://localhost:8082${NC}"
fi

echo ""
echo -e "${CYAN}Useful Commands:${NC}"
echo -e "  View logs:        ${YELLOW}docker-compose logs -f${NC}"
echo -e "  Stop services:    ${YELLOW}docker-compose down${NC}"
echo -e "  Restart service:  ${YELLOW}docker-compose restart <service>${NC}"
echo ""

