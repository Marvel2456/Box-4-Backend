#!/bin/bash
# ==============================================================================
# Box-4 Backend Production Deployment Script for VPS
# ==============================================================================

set -e

# Terminal colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}==============================================================================${NC}"
echo -e "${YELLOW} Starting Box-4 Backend Production Deployment ${NC}"
echo -e "${YELLOW}==============================================================================${NC}"

# 1. Pull latest code from Git repository
if [ -d ".git" ]; then
    echo -e "${GREEN}--> Fetching latest changes from git repository...${NC}"
    git pull origin main || git pull origin master
fi

# 2. Check for production environment file (.env.prod or .env)
ENV_FILE=".env.prod"
if [ ! -f ".env.prod" ]; then
    if [ -f ".env" ]; then
        ENV_FILE=".env"
    else
        echo -e "${RED}Error: Neither .env.prod nor .env file exists! Please copy .env.example to .env.prod and set production values.${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}--> Using environment config file: ${ENV_FILE}${NC}"

# 3. Determine docker compose command format (docker compose vs docker-compose)
DOCKER_COMPOSE_CMD="docker compose"
if ! docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
fi

# 4. Build and launch Docker services in detached mode
echo -e "${GREEN}--> Building and starting Docker containers...${NC}"
$DOCKER_COMPOSE_CMD -f docker-compose.prod.yml --env-file ${ENV_FILE} up -d --build --remove-orphans

# 5. Wait for containers and database initialization
echo -e "${GREEN}--> Waiting for container startup...${NC}"
sleep 5

# 6. Apply database migrations
echo -e "${GREEN}--> Running database migrations...${NC}"
$DOCKER_COMPOSE_CMD -f docker-compose.prod.yml --env-file ${ENV_FILE} exec -T web python manage.py migrate --no-input

# 7. Collect static files
echo -e "${GREEN}--> Collecting static files...${NC}"
$DOCKER_COMPOSE_CMD -f docker-compose.prod.yml --env-file ${ENV_FILE} exec -T web python manage.py collectstatic --no-input

# 8. Container health and status check
echo -e "${GREEN}--> Checking container status:${NC}"
$DOCKER_COMPOSE_CMD -f docker-compose.prod.yml --env-file ${ENV_FILE} ps

echo -e "${GREEN}==============================================================================${NC}"
echo -e "${GREEN} Box-4 Backend deployed successfully! ${NC}"
echo -e "${GREEN}==============================================================================${NC}"
