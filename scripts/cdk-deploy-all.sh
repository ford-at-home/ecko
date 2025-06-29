#!/bin/bash

# Complete CDK Deployment Script with Frontend Automation
# Deploys all stacks and automatically configures and deploys frontend

set -e

# Configuration
ENVIRONMENT="${1:-dev}"
AWS_PROFILE="${AWS_PROFILE:-personal}"
AWS_REGION="${AWS_REGION:-us-east-1}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CDK_DIR="$SCRIPT_DIR/../cdk"
FRONTEND_DIR="$SCRIPT_DIR/../frontend"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Progress tracking
TOTAL_STEPS=8
CURRENT_STEP=0

# Function to show progress
show_progress() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    echo -e "\n${BLUE}[$CURRENT_STEP/$TOTAL_STEPS]${NC} $1"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Function to check prerequisites
check_prerequisites() {
    show_progress "Checking prerequisites..."
    
    # Check for required tools
    local missing_tools=()
    
    command -v aws &> /dev/null || missing_tools+=("aws")
    command -v cdk &> /dev/null || missing_tools+=("cdk")
    command -v npm &> /dev/null || missing_tools+=("npm")
    command -v node &> /dev/null || missing_tools+=("node")
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        echo -e "${RED}❌ Error: Missing required tools: ${missing_tools[*]}${NC}"
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity --profile "$AWS_PROFILE" &> /dev/null; then
        echo -e "${RED}❌ Error: AWS credentials not configured for profile '$AWS_PROFILE'${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ All prerequisites met${NC}"
}

# Function to bootstrap CDK
bootstrap_cdk() {
    show_progress "Bootstrapping CDK (if needed)..."
    
    cd "$CDK_DIR"
    
    if ! aws cloudformation describe-stacks \
        --stack-name "CDKToolkit" \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" &> /dev/null; then
        
        echo "CDK not bootstrapped. Running bootstrap..."
        cdk bootstrap aws://$AWS_ACCOUNT/$AWS_REGION \
            --profile "$AWS_PROFILE"
    else
        echo -e "${GREEN}✅ CDK already bootstrapped${NC}"
    fi
}

# Function to install CDK dependencies
install_cdk_dependencies() {
    show_progress "Installing CDK dependencies..."
    
    cd "$CDK_DIR"
    
    if [ ! -d "node_modules" ] || [ package.json -nt node_modules ]; then
        npm install
    else
        echo -e "${GREEN}✅ CDK dependencies up to date${NC}"
    fi
}

# Function to build CDK
build_cdk() {
    show_progress "Building CDK application..."
    
    cd "$CDK_DIR"
    npm run build
    
    echo -e "${GREEN}✅ CDK built successfully${NC}"
}

# Function to deploy CDK stacks
deploy_cdk_stacks() {
    show_progress "Deploying CDK stacks..."
    
    cd "$CDK_DIR"
    
    # Deploy all stacks with automatic approval
    cdk deploy --all \
        --require-approval never \
        --profile "$AWS_PROFILE" \
        -c environment="$ENVIRONMENT"
    
    echo -e "${GREEN}✅ All CDK stacks deployed${NC}"
}

# Function to build frontend
build_frontend() {
    show_progress "Building frontend application..."
    
    # The frontend deployment script will handle this
    # but we ensure dependencies are installed
    cd "$FRONTEND_DIR"
    
    if [ ! -d "node_modules" ] || [ package.json -nt node_modules ]; then
        npm install
    fi
    
    echo -e "${GREEN}✅ Frontend dependencies ready${NC}"
}

# Function to deploy frontend
deploy_frontend() {
    show_progress "Deploying frontend with CDK configuration..."
    
    # Use the CDK-based frontend deployment script
    "$SCRIPT_DIR/cdk-deploy-frontend.sh" "$ENVIRONMENT"
    
    echo -e "${GREEN}✅ Frontend deployed${NC}"
}

# Function to run post-deployment tests
run_post_deployment_tests() {
    show_progress "Running post-deployment tests..."
    
    # Get API URL from CDK output
    API_URL=$(aws cloudformation describe-stacks \
        --stack-name "Echoes-${ENVIRONMENT}-Api" \
        --query "Stacks[0].Outputs[?OutputKey=='ApiGatewayUrl'].OutputValue" \
        --output text \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION")
    
    if [ -n "$API_URL" ]; then
        echo "Testing API health endpoint..."
        if curl -s "$API_URL/health" | grep -q "ok"; then
            echo -e "${GREEN}✅ API health check passed${NC}"
        else
            echo -e "${YELLOW}⚠️  Warning: API health check failed${NC}"
        fi
    fi
    
    # Get CloudFront URL
    CLOUDFRONT_URL=$(aws cloudformation describe-stacks \
        --stack-name "Echoes-${ENVIRONMENT}-Network" \
        --query "Stacks[0].Outputs[?OutputKey=='FrontendUrl'].OutputValue" \
        --output text \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" 2>/dev/null || echo "")
    
    if [ -n "$CLOUDFRONT_URL" ]; then
        echo "Testing frontend availability..."
        if curl -s -o /dev/null -w "%{http_code}" "$CLOUDFRONT_URL" | grep -q "200"; then
            echo -e "${GREEN}✅ Frontend is accessible${NC}"
        else
            echo -e "${YELLOW}⚠️  Warning: Frontend may not be fully deployed yet${NC}"
        fi
    fi
}

# Function to display deployment summary
display_summary() {
    echo -e "\n${GREEN}🎉 Deployment Complete!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "Environment: ${BLUE}$ENVIRONMENT${NC}"
    echo ""
    
    # Get and display all relevant URLs
    API_URL=$(aws cloudformation describe-stacks \
        --stack-name "Echoes-${ENVIRONMENT}-Api" \
        --query "Stacks[0].Outputs[?OutputKey=='ApiGatewayUrl'].OutputValue" \
        --output text \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" 2>/dev/null || echo "N/A")
    
    CLOUDFRONT_URL=$(aws cloudformation describe-stacks \
        --stack-name "Echoes-${ENVIRONMENT}-Network" \
        --query "Stacks[0].Outputs[?OutputKey=='FrontendUrl'].OutputValue" \
        --output text \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" 2>/dev/null || echo "N/A")
    
    echo -e "🌐 Frontend URL: ${BLUE}${CLOUDFRONT_URL}${NC}"
    echo -e "🔌 API URL: ${BLUE}${API_URL}${NC}"
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo -e "1. Visit the frontend URL to test the application"
    echo -e "2. Create a test account and verify email"
    echo -e "3. Test audio recording and playback"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Function to save deployment log
save_deployment_log() {
    local log_file="$SCRIPT_DIR/../deployment-logs/deployment-$(date +%Y%m%d-%H%M%S).log"
    mkdir -p "$(dirname "$log_file")"
    
    cat > "$log_file" << EOF
Deployment Log
==============
Date: $(date)
Environment: $ENVIRONMENT
AWS Profile: $AWS_PROFILE
AWS Region: $AWS_REGION
AWS Account: $AWS_ACCOUNT

Deployed Stacks:
EOF
    
    # List all deployed stacks
    aws cloudformation list-stacks \
        --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query "StackSummaries[?contains(StackName, 'Echoes-$ENVIRONMENT')].{Name:StackName,Status:StackStatus,Updated:LastUpdatedTime}" \
        --output table >> "$log_file"
    
    echo "" >> "$log_file"
    echo "Stack Outputs:" >> "$log_file"
    
    # Get outputs from all stacks
    for stack in Storage Auth Api Notif Frontend Network; do
        echo "" >> "$log_file"
        echo "Stack: Echoes-$ENVIRONMENT-$stack" >> "$log_file"
        aws cloudformation describe-stacks \
            --stack-name "Echoes-$ENVIRONMENT-$stack" \
            --profile "$AWS_PROFILE" \
            --region "$AWS_REGION" \
            --query "Stacks[0].Outputs[].[OutputKey,OutputValue]" \
            --output table 2>/dev/null >> "$log_file" || echo "Stack not found" >> "$log_file"
    done
    
    echo -e "\n${GREEN}📄 Deployment log saved to: $log_file${NC}"
}

# Main deployment flow
main() {
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}   Echoes Complete CDK Deployment${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    # Get AWS account ID
    AWS_ACCOUNT=$(aws sts get-caller-identity \
        --query Account \
        --output text \
        --profile "$AWS_PROFILE")
    
    echo -e "AWS Account: ${BLUE}$AWS_ACCOUNT${NC}"
    echo -e "Environment: ${BLUE}$ENVIRONMENT${NC}"
    echo -e "Region: ${BLUE}$AWS_REGION${NC}"
    echo ""
    
    # Run deployment steps
    check_prerequisites
    bootstrap_cdk
    install_cdk_dependencies
    build_cdk
    deploy_cdk_stacks
    build_frontend
    deploy_frontend
    run_post_deployment_tests
    
    # Save deployment log
    save_deployment_log
    
    # Display summary
    display_summary
}

# Handle script arguments
case "${2:-}" in
    --help|-h)
        echo "Usage: $0 [environment] [options]"
        echo ""
        echo "Arguments:"
        echo "  environment    Deployment environment (default: dev)"
        echo ""
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo ""
        echo "Environment variables:"
        echo "  AWS_PROFILE    AWS profile to use (default: personal)"
        echo "  AWS_REGION     AWS region to deploy to (default: us-east-1)"
        exit 0
        ;;
esac

# Run main function
main

# Exit successfully
exit 0