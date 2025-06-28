#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Default values
ENVIRONMENT="dev"
PLATFORM="web"
BUILD_ONLY=false
FORCE=false
SKIP_TESTS=false
SKIP_BUILD=false
INVALIDATE_CACHE=true

# Usage function
usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -e, --environment <env>    Target environment (dev, staging, prod) [default: dev]"
    echo "  -p, --platform <platform>  Platform to deploy (web, mobile, both) [default: web]"
    echo "  -b, --build-only           Build only, don't deploy"
    echo "  -f, --force                Force deployment without confirmation"
    echo "  --skip-tests               Skip running tests"
    echo "  --skip-build               Skip build step (use existing build)"
    echo "  --no-cache-invalidation    Skip CloudFront cache invalidation"
    echo "  -h, --help                 Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -e dev                                    # Deploy web to dev"
    echo "  $0 -e prod -p mobile                        # Deploy mobile to prod"
    echo "  $0 -e staging -p both                       # Deploy both platforms to staging"
    echo "  $0 -e dev -b                                # Build only for dev"
    echo ""
    echo "Platforms:"
    echo "  web     - React web application"
    echo "  mobile  - React Native/Expo mobile app"
    echo "  both    - Both web and mobile"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -p|--platform)
            PLATFORM="$2"
            shift 2
            ;;
        -b|--build-only)
            BUILD_ONLY=true
            shift
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --no-cache-invalidation)
            INVALIDATE_CACHE=false
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            usage
            exit 1
            ;;
    esac
done

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    echo -e "${RED}❌ Invalid environment: $ENVIRONMENT${NC}"
    echo "Valid environments: dev, staging, prod"
    exit 1
fi

# Validate platform
if [[ ! "$PLATFORM" =~ ^(web|mobile|both)$ ]]; then
    echo -e "${RED}❌ Invalid platform: $PLATFORM${NC}"
    echo "Valid platforms: web, mobile, both"
    exit 1
fi

echo -e "${BLUE}🎨 Echoes Frontend Deployment${NC}"
echo -e "${BLUE}=============================${NC}"
echo -e "${BLUE}Environment:${NC} $ENVIRONMENT"
echo -e "${BLUE}Platform:${NC} $PLATFORM"
echo -e "${BLUE}Build Only:${NC} $([ "$BUILD_ONLY" = true ] && echo "YES" || echo "NO")"
echo ""

# Load environment configuration
ENV_FILE="$PROJECT_ROOT/environments/$ENVIRONMENT/.env.frontend"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Environment file not found: $ENV_FILE${NC}"
    exit 1
fi

echo -e "${BLUE}📋 Loading environment configuration...${NC}"
set -a
source "$ENV_FILE"
set +a

# Check required tools
echo -e "${BLUE}🔧 Checking required tools...${NC}"

command -v node >/dev/null 2>&1 || { 
    echo -e "${RED}❌ Node.js is required but not installed.${NC}"
    exit 1
}

command -v npm >/dev/null 2>&1 || { 
    echo -e "${RED}❌ npm is required but not installed.${NC}"
    exit 1
}

if [ "$BUILD_ONLY" = false ]; then
    command -v aws >/dev/null 2>&1 || { 
        echo -e "${RED}❌ AWS CLI is required for deployment but not installed.${NC}"
        exit 1
    }
fi

if [[ "$PLATFORM" =~ ^(mobile|both)$ ]]; then
    command -v expo >/dev/null 2>&1 || { 
        echo -e "${RED}❌ Expo CLI is required for mobile deployment but not installed.${NC}"
        exit 1
    }
fi

# Navigate to project root
cd "$PROJECT_ROOT"

# Install dependencies
echo -e "${BLUE}📦 Installing dependencies...${NC}"
npm ci

# Generate build metadata
BUILD_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
GIT_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
VERSION="${BUILD_TIME}-$(echo $GIT_COMMIT | cut -c1-8)"

echo -e "${BLUE}📋 Build metadata:${NC}"
echo "Version: $VERSION"
echo "Build Time: $BUILD_TIME"
echo "Git Commit: $GIT_COMMIT"

# Function to build web application
build_web() {
    echo -e "${BLUE}🌐 Building web application...${NC}"
    
    # Set build environment variables
    export REACT_APP_VERSION="$VERSION"
    export REACT_APP_BUILD_TIME="$BUILD_TIME"
    export REACT_APP_GIT_COMMIT="$GIT_COMMIT"
    
    # Build the application
    if [ "$ENVIRONMENT" = "prod" ]; then
        npm run build:web:prod
    else
        npm run build:web
    fi
    
    echo -e "${GREEN}✅ Web application built successfully${NC}"
    
    # Generate build report
    echo -e "${BLUE}📊 Generating build report...${NC}"
    npm run analyze:web || echo "Build analysis not available"
    
    # List build contents
    echo -e "${BLUE}📁 Build contents:${NC}"
    ls -la build/ || ls -la dist/
}

# Function to build mobile application
build_mobile() {
    echo -e "${BLUE}📱 Building mobile application...${NC}"
    
    # Set build environment variables
    export EXPO_PUBLIC_VERSION="$VERSION"
    export EXPO_PUBLIC_BUILD_TIME="$BUILD_TIME"
    export EXPO_PUBLIC_GIT_COMMIT="$GIT_COMMIT"
    
    # Build for web (Expo web build)
    if [ "$ENVIRONMENT" = "prod" ]; then
        expo build:web --no-minify
    else
        expo build:web
    fi
    
    echo -e "${GREEN}✅ Mobile application built successfully${NC}"
    
    # List build contents
    echo -e "${BLUE}📁 Build contents:${NC}"
    ls -la web-build/
}

# Function to run tests
run_tests() {
    local platform="$1"
    
    if [ "$SKIP_TESTS" = true ]; then
        echo -e "${YELLOW}⏭️  Skipping tests${NC}"
        return 0
    fi
    
    echo -e "${BLUE}🧪 Running tests for $platform...${NC}"
    
    case $platform in
        web)
            npm run test:web || {
                echo -e "${RED}❌ Web tests failed${NC}"
                exit 1
            }
            ;;
        mobile)
            npm run test:mobile || {
                echo -e "${RED}❌ Mobile tests failed${NC}"
                exit 1
            }
            ;;
    esac
    
    echo -e "${GREEN}✅ Tests passed for $platform${NC}"
}

# Function to deploy to S3
deploy_to_s3() {
    local platform="$1"
    local build_dir="$2"
    local bucket_name="$3"
    
    echo -e "${BLUE}☁️  Deploying $platform to S3 bucket: $bucket_name${NC}"
    
    # Check if bucket exists
    if ! aws s3api head-bucket --bucket "$bucket_name" 2>/dev/null; then
        echo -e "${RED}❌ S3 bucket does not exist: $bucket_name${NC}"
        exit 1
    fi
    
    # Sync files to S3
    aws s3 sync "$build_dir/" "s3://$bucket_name/" \
        --exclude "*.map" \
        --cache-control "public,max-age=31536000,immutable" \
        --metadata-directive REPLACE \
        --metadata version="$VERSION"
    
    # Set special cache control for HTML files
    find "$build_dir" -name "*.html" -exec basename {} \; | while read -r html_file; do
        aws s3 cp "s3://$bucket_name/$html_file" "s3://$bucket_name/$html_file" \
            --cache-control "public,max-age=0,must-revalidate" \
            --metadata-directive REPLACE \
            --metadata version="$VERSION"
    done
    
    echo -e "${GREEN}✅ Successfully deployed $platform to S3${NC}"
}

# Function to invalidate CloudFront cache
invalidate_cloudfront() {
    local distribution_id="$1"
    
    if [ "$INVALIDATE_CACHE" = false ]; then
        echo -e "${YELLOW}⏭️  Skipping CloudFront cache invalidation${NC}"
        return 0
    fi
    
    if [ -z "$distribution_id" ]; then
        echo -e "${YELLOW}⚠️  CloudFront distribution ID not found, skipping invalidation${NC}"
        return 0
    fi
    
    echo -e "${BLUE}🔄 Invalidating CloudFront cache...${NC}"
    
    INVALIDATION_ID=$(aws cloudfront create-invalidation \
        --distribution-id "$distribution_id" \
        --paths "/*" \
        --query 'Invalidation.Id' \
        --output text)
    
    echo -e "${GREEN}✅ CloudFront invalidation created: $INVALIDATION_ID${NC}"
    
    # Wait for invalidation to complete (optional)
    echo -e "${BLUE}⏳ Waiting for invalidation to complete...${NC}"
    aws cloudfront wait invalidation-completed \
        --distribution-id "$distribution_id" \
        --id "$INVALIDATION_ID" || true
    
    echo -e "${GREEN}✅ CloudFront invalidation completed${NC}"
}

# Function to deploy web platform
deploy_web() {
    echo -e "${BLUE}🌐 Deploying web platform...${NC}"
    
    if [ "$SKIP_BUILD" = false ]; then
        run_tests "web"
        build_web
    fi
    
    if [ "$BUILD_ONLY" = false ]; then
        # Get infrastructure outputs
        INFRA_OUTPUTS="$PROJECT_ROOT/cdk/outputs-storage-$ENVIRONMENT.json"
        if [ -f "$INFRA_OUTPUTS" ]; then
            WEB_BUCKET=$(jq -r ".\"EchoesStorageStack-$ENVIRONMENT\".WebBucketName" "$INFRA_OUTPUTS" 2>/dev/null || echo "echoes-web-$ENVIRONMENT")
            DISTRIBUTION_ID=$(jq -r ".\"EchoesWebStack-$ENVIRONMENT\".DistributionId" "$INFRA_OUTPUTS" 2>/dev/null || echo "")
        else
            WEB_BUCKET="echoes-web-$ENVIRONMENT"
            DISTRIBUTION_ID=""
        fi
        
        deploy_to_s3 "web" "build" "$WEB_BUCKET"
        invalidate_cloudfront "$DISTRIBUTION_ID"
        
        # Get website URL
        WEBSITE_URL="https://$WEB_BUCKET.s3.amazonaws.com"
        if [ -n "$DISTRIBUTION_ID" ]; then
            DOMAIN_NAME=$(aws cloudfront get-distribution --id "$DISTRIBUTION_ID" --query 'Distribution.DomainName' --output text)
            WEBSITE_URL="https://$DOMAIN_NAME"
        fi
        
        echo -e "${GREEN}🌐 Web application deployed successfully!${NC}"
        echo -e "${BLUE}URL: $WEBSITE_URL${NC}"
    fi
}

# Function to deploy mobile platform
deploy_mobile() {
    echo -e "${BLUE}📱 Deploying mobile platform...${NC}"
    
    if [ "$SKIP_BUILD" = false ]; then
        run_tests "mobile"
        build_mobile
    fi
    
    if [ "$BUILD_ONLY" = false ]; then
        if [ "$ENVIRONMENT" = "prod" ]; then
            # Deploy to app stores (requires Expo credentials)
            echo -e "${BLUE}🏪 Deploying to app stores...${NC}"
            
            if [ -n "$EXPO_TOKEN" ]; then
                echo "$EXPO_TOKEN" | expo login --non-interactive
                
                # Build and submit iOS
                if [ "${DEPLOY_IOS:-false}" = "true" ]; then
                    echo -e "${BLUE}🍎 Building and submitting iOS app...${NC}"
                    eas build --platform ios --profile production --wait
                    eas submit --platform ios --profile production
                fi
                
                # Build and submit Android
                if [ "${DEPLOY_ANDROID:-false}" = "true" ]; then
                    echo -e "${BLUE}🤖 Building and submitting Android app...${NC}"
                    eas build --platform android --profile production --wait
                    eas submit --platform android --profile production
                fi
            else
                echo -e "${YELLOW}⚠️  EXPO_TOKEN not set, skipping app store deployment${NC}"
            fi
        else
            # Deploy web build to S3 for non-prod environments
            MOBILE_BUCKET="echoes-mobile-$ENVIRONMENT"
            deploy_to_s3 "mobile" "web-build" "$MOBILE_BUCKET"
            
            MOBILE_URL="https://$MOBILE_BUCKET.s3.amazonaws.com"
            echo -e "${GREEN}📱 Mobile web application deployed successfully!${NC}"
            echo -e "${BLUE}URL: $MOBILE_URL${NC}"
        fi
    fi
}

# Main deployment logic
case $PLATFORM in
    web)
        deploy_web
        ;;
    mobile)
        deploy_mobile
        ;;
    both)
        deploy_web
        echo ""
        deploy_mobile
        ;;
esac

# Save deployment information
DEPLOYMENT_INFO="$PROJECT_ROOT/tmp/frontend-deployment-$ENVIRONMENT.json"
mkdir -p "$(dirname "$DEPLOYMENT_INFO")"

cat > "$DEPLOYMENT_INFO" << EOF
{
  "environment": "$ENVIRONMENT",
  "platform": "$PLATFORM",
  "version": "$VERSION",
  "build_time": "$BUILD_TIME",
  "git_commit": "$GIT_COMMIT",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "build_only": $BUILD_ONLY,
  "deployed_by": "$(whoami)"
}
EOF

echo -e "${GREEN}"
echo "================================================================="
echo "🎉 Frontend deployment completed successfully!"
echo "================================================================="
echo -e "${NC}"
echo -e "${BLUE}Deployment Summary:${NC}"
echo "Environment: $ENVIRONMENT"
echo "Platform: $PLATFORM"
echo "Version: $VERSION"
echo "Build Time: $BUILD_TIME"
echo ""
echo -e "${BLUE}Deployment info saved to: $DEPLOYMENT_INFO${NC}"

if [ "$BUILD_ONLY" = false ]; then
    echo ""
    echo -e "${BLUE}Next Steps:${NC}"
    echo "1. Run E2E tests: npm run test:e2e"
    echo "2. Performance audit: npm run audit:lighthouse"
    echo "3. Monitor deployment: check CloudWatch logs and metrics"
fi