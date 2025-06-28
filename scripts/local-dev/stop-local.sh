#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🛑 Stopping Echoes Local Development Environment${NC}"
echo -e "${BLUE}================================================${NC}"

# Parse command line arguments
REMOVE_VOLUMES=false
REMOVE_IMAGES=false
KEEP_DATA=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --remove-volumes)
            REMOVE_VOLUMES=true
            shift
            ;;
        --remove-images)
            REMOVE_IMAGES=true
            shift
            ;;
        --keep-data)
            KEEP_DATA=true
            shift
            ;;
        --clean-all)
            REMOVE_VOLUMES=true
            REMOVE_IMAGES=true
            KEEP_DATA=false
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --remove-volumes    Remove all volumes (loses data)"
            echo "  --remove-images     Remove downloaded images"
            echo "  --keep-data         Keep LocalStack and database data"
            echo "  --clean-all         Remove everything (volumes + images)"
            echo "  --help, -h          Show this help"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Stop SAM Local if running
if [ -f tmp/sam-local/sam.pid ]; then
    SAM_PID=$(cat tmp/sam-local/sam.pid)
    echo -e "${YELLOW}🛑 Stopping SAM Local API (PID: $SAM_PID)...${NC}"
    
    if kill -0 $SAM_PID 2>/dev/null; then
        kill $SAM_PID
        echo -e "${GREEN}✅ SAM Local API stopped${NC}"
    else
        echo -e "${YELLOW}⚠️  SAM Local API was not running${NC}"
    fi
    
    rm -f tmp/sam-local/sam.pid
fi

# Stop Docker Compose services
echo -e "${BLUE}🐳 Stopping Docker services...${NC}"

docker-compose -f docker-compose.local.yml down

# Remove volumes if requested
if [ "$REMOVE_VOLUMES" = true ]; then
    echo -e "${YELLOW}🗑️  Removing volumes...${NC}"
    docker-compose -f docker-compose.local.yml down -v
    
    # Remove named volumes
    docker volume rm echoes_postgres_data 2>/dev/null || true
    docker volume rm echoes_redis_data 2>/dev/null || true
    
    echo -e "${GREEN}✅ Volumes removed${NC}"
fi

# Remove images if requested
if [ "$REMOVE_IMAGES" = true ]; then
    echo -e "${YELLOW}🗑️  Removing images...${NC}"
    
    # Remove LocalStack images
    docker rmi localstack/localstack:3.0 2>/dev/null || true
    
    # Remove other images
    docker rmi postgres:15-alpine 2>/dev/null || true
    docker rmi redis:7-alpine 2>/dev/null || true
    docker rmi mailhog/mailhog:latest 2>/dev/null || true
    docker rmi amazon/aws-cli:latest 2>/dev/null || true
    docker rmi aaronshaf/dynamodb-admin:latest 2>/dev/null || true
    
    echo -e "${GREEN}✅ Images removed${NC}"
fi

# Clean up local data if not keeping it
if [ "$KEEP_DATA" = false ]; then
    echo -e "${YELLOW}🧹 Cleaning up local data...${NC}"
    
    # Remove LocalStack data
    rm -rf tmp/localstack/data/* 2>/dev/null || true
    
    # Remove temporary files
    rm -f tmp/local-services.json 2>/dev/null || true
    rm -f /tmp/localstack-config.json 2>/dev/null || true
    
    # Remove logs
    rm -f logs/sam-local.log 2>/dev/null || true
    
    echo -e "${GREEN}✅ Local data cleaned${NC}"
fi

# Remove SAM artifacts
echo -e "${BLUE}🧹 Cleaning SAM artifacts...${NC}"
rm -f samconfig.toml 2>/dev/null || true
rm -rf .aws-sam 2>/dev/null || true

# Clean up Docker if requested
if [ "$REMOVE_VOLUMES" = true ] || [ "$REMOVE_IMAGES" = true ]; then
    echo -e "${BLUE}🧹 Running Docker system cleanup...${NC}"
    docker system prune -f
fi

# Remove network if it exists and is not being used
NETWORK_EXISTS=$(docker network ls --filter name=echoes_local -q)
if [ ! -z "$NETWORK_EXISTS" ]; then
    echo -e "${YELLOW}🌐 Removing Docker network...${NC}"
    docker network rm echoes_local 2>/dev/null || true
fi

echo -e "${GREEN}"
echo "================================================================="
echo "🏁 Echoes Local Development Environment stopped!"
echo "================================================================="
echo -e "${NC}"

if [ "$KEEP_DATA" = true ]; then
    echo -e "${BLUE}💾 Data has been preserved in:${NC}"
    echo "   - tmp/localstack/ (LocalStack data)"
    echo "   - Docker volumes (PostgreSQL, Redis)"
    echo ""
    echo -e "${YELLOW}💡 Run './scripts/local-dev/start-local.sh' to resume with existing data${NC}"
else
    echo -e "${YELLOW}🗑️  All local data has been cleaned up${NC}"
    echo -e "${BLUE}💡 Next startup will create fresh databases and services${NC}"
fi

echo ""
echo -e "${BLUE}Useful commands:${NC}"
echo "🚀 Start fresh:                 ./scripts/local-dev/start-local.sh"
echo "📊 Check Docker status:         docker ps"
echo "🧹 Clean Docker completely:     docker system prune -a"