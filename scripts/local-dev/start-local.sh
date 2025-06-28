#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🌀 Starting Echoes Local Development Environment${NC}"
echo -e "${BLUE}=================================================${NC}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

# Check if required tools are installed
command -v docker-compose >/dev/null 2>&1 || { 
    echo -e "${RED}❌ docker-compose is required but not installed.${NC}"; 
    exit 1; 
}

command -v sam >/dev/null 2>&1 || { 
    echo -e "${YELLOW}⚠️  SAM CLI is not installed. Some features may not work.${NC}"; 
}

# Parse command line arguments
SERVICES="all"
FORCE_RECREATE=false
BACKGROUND=false
SAM_LOCAL=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --services)
            SERVICES="$2"
            shift 2
            ;;
        --force-recreate)
            FORCE_RECREATE=true
            shift
            ;;
        --background|-d)
            BACKGROUND=true
            shift
            ;;
        --sam-local)
            SAM_LOCAL=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --services <services>    Start specific services (comma-separated)"
            echo "  --force-recreate        Force recreate containers"
            echo "  --background, -d        Run in background"
            echo "  --sam-local            Start SAM local API"
            echo "  --help, -h             Show this help"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Create necessary directories
echo -e "${BLUE}📁 Creating directories...${NC}"
mkdir -p tmp/localstack/data
mkdir -p tmp/sam-local
mkdir -p logs

# Create .env.local if it doesn't exist
if [ ! -f .env.local ]; then
    echo -e "${BLUE}📝 Creating .env.local...${NC}"
    cat > .env.local << EOF
# Local Development Environment Variables
ENVIRONMENT=dev
DEBUG=1
LOCALSTACK_VOLUME_DIR=./tmp/localstack

# Database
POSTGRES_DB=echoes_dev
POSTGRES_USER=echoes_user
POSTGRES_PASSWORD=echoes_password

# LocalStack
LOCALSTACK_ENDPOINT=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_DEFAULT_REGION=us-east-1

# API
API_PORT=8000
FRONTEND_PORT=3000
EOF
fi

# Load environment variables
source .env.local

# Docker Compose command setup
COMPOSE_CMD="docker-compose -f docker-compose.local.yml"
COMPOSE_ARGS=""

if [ "$FORCE_RECREATE" = true ]; then
    COMPOSE_ARGS="$COMPOSE_ARGS --force-recreate"
fi

if [ "$BACKGROUND" = true ]; then
    COMPOSE_ARGS="$COMPOSE_ARGS -d"
fi

# Start services
echo -e "${BLUE}🐳 Starting Docker services...${NC}"

if [ "$SERVICES" = "all" ]; then
    $COMPOSE_CMD up $COMPOSE_ARGS
else
    IFS=',' read -ra SERVICE_ARRAY <<< "$SERVICES"
    $COMPOSE_CMD up $COMPOSE_ARGS "${SERVICE_ARRAY[@]}"
fi

# Wait for LocalStack to be ready
echo -e "${BLUE}⏳ Waiting for LocalStack to be ready...${NC}"
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if curl -s http://localhost:4566/_localstack/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ LocalStack is ready!${NC}"
        break
    fi
    
    attempt=$((attempt + 1))
    echo -e "${YELLOW}⏳ Attempt $attempt/$max_attempts - waiting for LocalStack...${NC}"
    sleep 5
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "${RED}❌ LocalStack failed to start after $max_attempts attempts${NC}"
    exit 1
fi

# Start SAM Local if requested
if [ "$SAM_LOCAL" = true ] && command -v sam >/dev/null 2>&1; then
    echo -e "${BLUE}🚀 Starting SAM Local API...${NC}"
    
    # Create samconfig.toml for local development
    cat > samconfig.toml << EOF
version = 0.1
[default.local_start_api.parameters]
docker_network = "echoes_local"
host = "0.0.0.0"
port = 3001
env_vars = "environments/dev/.env.backend"
parameter_overrides = "Environment=dev"
EOF

    # Start SAM local in background
    nohup sam local start-api \
        --template sam-template.local.yml \
        --docker-network echoes_local \
        --host 0.0.0.0 \
        --port 3001 \
        --env-vars environments/dev/.env.backend \
        --parameter-overrides Environment=dev \
        > logs/sam-local.log 2>&1 &
    
    SAM_PID=$!
    echo $SAM_PID > tmp/sam-local/sam.pid
    echo -e "${GREEN}✅ SAM Local API started on port 3001 (PID: $SAM_PID)${NC}"
fi

# Display helpful information
echo -e "${GREEN}"
echo "================================================================="
echo "🎉 Echoes Local Development Environment is ready!"
echo "================================================================="
echo -e "${NC}"
echo -e "${BLUE}Available Services:${NC}"
echo "🌐 Frontend (when started):     http://localhost:3000"
echo "🚀 SAM Local API (if enabled):  http://localhost:3001"
echo "🗄️  DynamoDB Admin:             http://localhost:8001"
echo "📧 MailHog (Email testing):     http://localhost:8025"
echo "☁️  LocalStack Health:          http://localhost:4566/_localstack/health"
echo "🐘 PostgreSQL:                  localhost:5432"
echo "🔴 Redis:                       localhost:6379"
echo ""
echo -e "${BLUE}Useful Commands:${NC}"
echo "📋 View LocalStack config:      cat /tmp/localstack-config.json"
echo "🔍 Check services:              docker-compose -f docker-compose.local.yml ps"
echo "📊 View logs:                   docker-compose -f docker-compose.local.yml logs -f"
echo "🛑 Stop services:               ./scripts/local-dev/stop-local.sh"
echo ""
echo -e "${BLUE}Test Credentials:${NC}"
echo "👤 Username: testuser@example.com"
echo "🔑 Password: TestPass123!"
echo ""
echo -e "${YELLOW}💡 Tip: Run './scripts/local-dev/test-local.sh' to verify everything is working${NC}"

# Save service information
cat > tmp/local-services.json << EOF
{
  "localstack": {
    "endpoint": "http://localhost:4566",
    "health": "http://localhost:4566/_localstack/health"
  },
  "dynamodb_admin": {
    "url": "http://localhost:8001"
  },
  "mailhog": {
    "url": "http://localhost:8025"
  },
  "postgres": {
    "host": "localhost",
    "port": 5432,
    "database": "echoes_dev",
    "username": "echoes_user"
  },
  "redis": {
    "host": "localhost",
    "port": 6379
  },
  "sam_local": {
    "api_url": "http://localhost:3001",
    "enabled": $SAM_LOCAL
  }
}
EOF

echo -e "${GREEN}🎯 Setup complete! Service information saved to tmp/local-services.json${NC}"