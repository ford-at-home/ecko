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
CDK_DIR="$PROJECT_ROOT/cdk"

# Default values
ENVIRONMENT="dev"
DESTROY=false
DIFF_ONLY=false
BOOTSTRAP=false
FORCE=false
STACK_NAMES=""
DRY_RUN=false

# Usage function
usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -e, --environment <env>    Target environment (dev, staging, prod) [default: dev]"
    echo "  -s, --stacks <stacks>      Comma-separated list of stacks to deploy"
    echo "  -d, --destroy              Destroy infrastructure instead of deploying"
    echo "  -c, --diff                 Show diff only, don't deploy"
    echo "  -b, --bootstrap            Bootstrap CDK before deployment"
    echo "  -f, --force                Force deployment without confirmation"
    echo "  --dry-run                  Show what would be deployed without executing"
    echo "  -h, --help                 Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -e dev                                    # Deploy all stacks to dev"
    echo "  $0 -e prod -s storage,auth                   # Deploy specific stacks to prod"
    echo "  $0 -e staging -c                            # Show diff for staging"
    echo "  $0 -e dev -d -f                             # Force destroy dev environment"
    echo ""
    echo "Available stacks: storage, auth, api, notifications"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -s|--stacks)
            STACK_NAMES="$2"
            shift 2
            ;;
        -d|--destroy)
            DESTROY=true
            shift
            ;;
        -c|--diff)
            DIFF_ONLY=true
            shift
            ;;
        -b|--bootstrap)
            BOOTSTRAP=true
            shift
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
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

# Available stacks
ALL_STACKS="storage auth api notifications"
if [ -z "$STACK_NAMES" ]; then
    DEPLOY_STACKS=$ALL_STACKS
else
    IFS=',' read -ra DEPLOY_STACKS <<< "$STACK_NAMES"
fi

echo -e "${BLUE}🏗️  Echoes Infrastructure Deployment${NC}"
echo -e "${BLUE}====================================${NC}"
echo -e "${BLUE}Environment:${NC} $ENVIRONMENT"
echo -e "${BLUE}Stacks:${NC} ${DEPLOY_STACKS[*]}"
echo -e "${BLUE}Action:${NC} $([ "$DESTROY" = true ] && echo "DESTROY" || echo "DEPLOY")"
echo ""

# Load environment configuration
ENV_FILE="$PROJECT_ROOT/environments/$ENVIRONMENT/.env.infrastructure"
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

command -v aws >/dev/null 2>&1 || { 
    echo -e "${RED}❌ AWS CLI is required but not installed.${NC}"
    exit 1
}

command -v cdk >/dev/null 2>&1 || { 
    echo -e "${RED}❌ CDK CLI is required but not installed.${NC}"
    exit 1
}

command -v node >/dev/null 2>&1 || { 
    echo -e "${RED}❌ Node.js is required but not installed.${NC}"
    exit 1
}

# Check AWS credentials
echo -e "${BLUE}🔐 Checking AWS credentials...${NC}"
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo -e "${RED}❌ AWS credentials not configured or invalid.${NC}"
    exit 1
fi

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region || echo "us-east-1")

echo -e "${GREEN}✅ AWS Account: $AWS_ACCOUNT_ID${NC}"
echo -e "${GREEN}✅ AWS Region: $AWS_REGION${NC}"

# Navigate to CDK directory
cd "$CDK_DIR"

# Install dependencies
echo -e "${BLUE}📦 Installing CDK dependencies...${NC}"
npm ci

# Bootstrap CDK if requested
if [ "$BOOTSTRAP" = true ]; then
    echo -e "${BLUE}🚀 Bootstrapping CDK...${NC}"
    cdk bootstrap aws://$AWS_ACCOUNT_ID/$AWS_REGION \
        --cloudformation-execution-policies arn:aws:iam::aws:policy/AdministratorAccess \
        --qualifier $(echo $ENVIRONMENT | cut -c1-8)echoes
fi

# Function to deploy a single stack
deploy_stack() {
    local stack_name="$1"
    local full_stack_name="Echoes$(echo ${stack_name^}Stack)-$ENVIRONMENT"
    
    echo -e "${BLUE}📋 Processing stack: $full_stack_name${NC}"
    
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}🔍 DRY RUN: Would deploy $full_stack_name${NC}"
        return 0
    fi
    
    if [ "$DIFF_ONLY" = true ]; then
        echo -e "${BLUE}🔍 Showing diff for $full_stack_name...${NC}"
        cdk diff "$full_stack_name" || true
        return 0
    fi
    
    if [ "$DESTROY" = true ]; then
        if [ "$FORCE" = false ]; then
            echo -e "${YELLOW}⚠️  Are you sure you want to destroy $full_stack_name? (y/N)${NC}"
            read -r confirmation
            if [[ ! $confirmation =~ ^[Yy]$ ]]; then
                echo -e "${YELLOW}⏭️  Skipping $full_stack_name${NC}"
                return 0
            fi
        fi
        
        echo -e "${RED}💥 Destroying $full_stack_name...${NC}"
        cdk destroy "$full_stack_name" --force
    else
        echo -e "${GREEN}🚀 Deploying $full_stack_name...${NC}"
        cdk deploy "$full_stack_name" \
            --require-approval never \
            --progress events \
            --outputs-file "outputs-$stack_name-$ENVIRONMENT.json"
    fi
}

# Function to get stack dependencies
get_stack_order() {
    case $1 in
        storage)
            echo "1"
            ;;
        auth)
            echo "2"
            ;;
        api)
            echo "3"
            ;;
        notifications)
            echo "4"
            ;;
        *)
            echo "999"
            ;;
    esac
}

# Sort stacks by deployment order
if [ "$DESTROY" = true ]; then
    # Reverse order for destruction
    sorted_stacks=($(printf '%s\n' "${DEPLOY_STACKS[@]}" | sort -rn -k1,1 -t',' --key=<(for stack in "${DEPLOY_STACKS[@]}"; do echo "$(get_stack_order $stack) $stack"; done | sort -rn | cut -d' ' -f2)))
else
    # Normal order for deployment
    sorted_stacks=($(printf '%s\n' "${DEPLOY_STACKS[@]}" | sort -n -k1,1 -t',' --key=<(for stack in "${DEPLOY_STACKS[@]}"; do echo "$(get_stack_order $stack) $stack"; done | sort -n | cut -d' ' -f2)))
fi

# Deploy/destroy stacks in order
for stack in "${sorted_stacks[@]}"; do
    if [[ " $ALL_STACKS " =~ " $stack " ]]; then
        deploy_stack "$stack"
    else
        echo -e "${RED}❌ Unknown stack: $stack${NC}"
        echo "Available stacks: $ALL_STACKS"
        exit 1
    fi
done

# Run post-deployment tests if deploying
if [ "$DESTROY" = false ] && [ "$DIFF_ONLY" = false ] && [ "$DRY_RUN" = false ]; then
    echo -e "${BLUE}🧪 Running post-deployment tests...${NC}"
    
    # Basic health checks
    for stack in "${sorted_stacks[@]}"; do
        case $stack in
            storage)
                echo -e "${BLUE}🗄️  Testing S3 bucket access...${NC}"
                # Test S3 bucket exists
                if aws s3api head-bucket --bucket "$S3_BUCKET_NAME" 2>/dev/null; then
                    echo -e "${GREEN}✅ S3 bucket accessible${NC}"
                else
                    echo -e "${RED}❌ S3 bucket not accessible${NC}"
                fi
                ;;
            auth)
                echo -e "${BLUE}👤 Testing Cognito User Pool...${NC}"
                # Test Cognito User Pool exists
                if aws cognito-idp describe-user-pool --user-pool-id "$COGNITO_USER_POOL_ID" >/dev/null 2>&1; then
                    echo -e "${GREEN}✅ Cognito User Pool accessible${NC}"
                else
                    echo -e "${RED}❌ Cognito User Pool not accessible${NC}"
                fi
                ;;
            api)
                echo -e "${BLUE}🚀 Testing API Gateway...${NC}"
                # Test API Gateway health endpoint (if available)
                API_URL=$(jq -r ".\"EchoesApiStack-$ENVIRONMENT\".ApiEndpoint" "outputs-api-$ENVIRONMENT.json" 2>/dev/null || echo "")
                if [ -n "$API_URL" ]; then
                    if curl -f "$API_URL/health" >/dev/null 2>&1; then
                        echo -e "${GREEN}✅ API Gateway accessible${NC}"
                    else
                        echo -e "${YELLOW}⚠️  API Gateway health check failed (may be normal)${NC}"
                    fi
                fi
                ;;
        esac
    done
fi

# Save deployment information
DEPLOYMENT_INFO="$PROJECT_ROOT/tmp/deployment-info-$ENVIRONMENT.json"
mkdir -p "$(dirname "$DEPLOYMENT_INFO")"

cat > "$DEPLOYMENT_INFO" << EOF
{
  "environment": "$ENVIRONMENT",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "action": "$([ "$DESTROY" = true ] && echo "destroy" || echo "deploy")",
  "stacks": $(printf '%s\n' "${sorted_stacks[@]}" | jq -R . | jq -s .),
  "aws_account": "$AWS_ACCOUNT_ID",
  "aws_region": "$AWS_REGION",
  "git_commit": "$(git rev-parse HEAD 2>/dev/null || echo "unknown")",
  "deployed_by": "$(whoami)"
}
EOF

echo -e "${GREEN}"
echo "================================================================="
echo "🎉 Infrastructure deployment completed successfully!"
echo "================================================================="
echo -e "${NC}"
echo -e "${BLUE}Deployment Summary:${NC}"
echo "Environment: $ENVIRONMENT"
echo "Action: $([ "$DESTROY" = true ] && echo "DESTROY" || echo "DEPLOY")"
echo "Stacks: ${sorted_stacks[*]}"
echo "AWS Account: $AWS_ACCOUNT_ID"
echo "AWS Region: $AWS_REGION"
echo ""
echo -e "${BLUE}Deployment info saved to: $DEPLOYMENT_INFO${NC}"

if [ "$DESTROY" = false ]; then
    echo ""
    echo -e "${BLUE}Next Steps:${NC}"
    echo "1. Deploy frontend: ./scripts/deployment/deploy-frontend.sh -e $ENVIRONMENT"
    echo "2. Run integration tests: ./scripts/deployment/test-deployment.sh -e $ENVIRONMENT"
    echo "3. View CloudFormation stacks: aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE"
fi