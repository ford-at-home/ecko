#!/bin/bash

# Echoes Backend Complete Deployment Script
# One-click deployment for AWS infrastructure and backend services
# Usage: ./deploy.sh [environment] [--destroy] [--no-confirm]

set -euo pipefail

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Color

# Script configuration
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$SCRIPT_DIR"
readonly DEPLOY_DIR="$PROJECT_ROOT/deploy"

# Default values
ENVIRONMENT="${1:-dev}"
DESTROY_MODE=false
NO_CONFIRM=false
AWS_PROFILE="default"
LOG_LEVEL="INFO"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -p|--profile)
            AWS_PROFILE="$2"
            shift 2
            ;;
        --destroy)
            DESTROY_MODE=true
            shift
            ;;
        --no-confirm)
            NO_CONFIRM=true
            shift
            ;;
        -v|--verbose)
            LOG_LEVEL="DEBUG"
            shift
            ;;
        -h|--help)
            cat << EOF
Echoes Backend Deployment Script

Usage: $0 [options] [environment]

Arguments:
  environment              Environment to deploy to (dev, staging, prod) [default: dev]

Options:
  -e, --environment <env>  Specify environment explicitly
  -p, --profile <profile>  AWS profile to use [default: default]
  --destroy               Destroy infrastructure instead of deploying
  --no-confirm            Skip confirmation prompts
  -v, --verbose           Enable verbose logging
  -h, --help              Show this help message

Examples:
  $0                      # Deploy to dev environment
  $0 prod                 # Deploy to production
  $0 -e staging --no-confirm  # Deploy to staging without confirmation
  $0 --destroy dev        # Destroy dev environment

For more advanced options, use scripts in the deploy/ directory.
EOF
            exit 0
            ;;
        *)
            if [[ "$1" =~ ^(dev|staging|prod)$ ]]; then
                ENVIRONMENT="$1"
                shift
            else
                echo -e "${RED}❌ Unknown option: $1${NC}" >&2
                exit 1
            fi
            ;;
    esac
done

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}" >&2
}

log_debug() {
    if [[ "$LOG_LEVEL" == "DEBUG" ]]; then
        echo -e "${PURPLE}🔍 $1${NC}"
    fi
}

# Print banner
print_banner() {
    echo -e "${CYAN}"
    cat << 'EOF'
 _____ _                     
|  ___| |                    
| |__ | |__   ___   ___  ___ 
|  __|| '_ \ / _ \ / _ \/ __|
| |___| | | | (_) |  __/\__ \
\____/|_| |_|\___/ \___||___/
                             
Backend Deployment Automation
EOF
    echo -e "${NC}"
    echo -e "${BLUE}Environment: ${ENVIRONMENT}${NC}"
    echo -e "${BLUE}AWS Profile: ${AWS_PROFILE}${NC}"
    echo -e "${BLUE}Action: $([ "$DESTROY_MODE" = true ] && echo "DESTROY" || echo "DEPLOY")${NC}"
    echo "================================="
}

# Validate environment
validate_environment() {
    log_info "Validating environment: $ENVIRONMENT"
    
    if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
        log_error "Invalid environment: $ENVIRONMENT"
        log_error "Valid environments: dev, staging, prod"
        exit 1
    fi
    
    log_success "Environment validation passed"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites"
    
    local missing_tools=()
    
    # Check required tools
    for tool in aws cdk node npm python3; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        log_error "Please install the missing tools and try again"
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity --profile "$AWS_PROFILE" &> /dev/null; then
        log_error "AWS credentials not configured for profile: $AWS_PROFILE"
        log_error "Please run: aws configure --profile $AWS_PROFILE"
        exit 1
    fi
    
    # Check Python version
    local python_version
    python_version=$(python3 --version | cut -d' ' -f2)
    if [[ "$(echo "$python_version" | cut -d. -f1-2)" < "3.8" ]]; then
        log_error "Python 3.8+ required, found: $python_version"
        exit 1
    fi
    
    log_success "All prerequisites met"
}

# Get AWS account info
get_aws_info() {
    log_info "Getting AWS account information"
    
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --profile "$AWS_PROFILE" --query Account --output text)
    AWS_REGION=$(aws configure get region --profile "$AWS_PROFILE" || echo "us-east-1")
    
    log_debug "AWS Account ID: $AWS_ACCOUNT_ID"
    log_debug "AWS Region: $AWS_REGION"
    
    export AWS_ACCOUNT_ID AWS_REGION
}

# Confirm deployment
confirm_deployment() {
    if [[ "$NO_CONFIRM" = true ]]; then
        return 0
    fi
    
    echo
    log_warning "You are about to $([ "$DESTROY_MODE" = true ] && echo "DESTROY" || echo "DEPLOY") the following:"
    echo "  Environment: $ENVIRONMENT"
    echo "  AWS Account: $AWS_ACCOUNT_ID"
    echo "  AWS Region: $AWS_REGION"
    echo "  AWS Profile: $AWS_PROFILE"
    echo
    
    if [[ "$DESTROY_MODE" = true ]]; then
        echo -e "${RED}⚠️  THIS WILL PERMANENTLY DELETE ALL RESOURCES IN THE $ENVIRONMENT ENVIRONMENT!${NC}"
        echo -e "${RED}⚠️  THIS ACTION CANNOT BE UNDONE!${NC}"
        echo
    fi
    
    read -p "Do you want to continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Deployment cancelled by user"
        exit 0
    fi
}

# Run deployment
run_deployment() {
    log_info "Starting deployment process"
    
    # Set environment variables
    export ENVIRONMENT AWS_PROFILE AWS_ACCOUNT_ID AWS_REGION
    
    if [[ "$DESTROY_MODE" = true ]]; then
        log_info "Running destroy process"
        "$DEPLOY_DIR/scripts/destroy.sh" --environment "$ENVIRONMENT" --profile "$AWS_PROFILE" --force
    else
        log_info "Running deployment process"
        
        # 1. Setup environment
        log_info "Step 1/7: Setting up environment configuration"
        "$DEPLOY_DIR/scripts/setup-environment.sh" --environment "$ENVIRONMENT"
        
        # 2. Prepare infrastructure
        log_info "Step 2/7: Preparing infrastructure templates"
        "$DEPLOY_DIR/scripts/prepare-infrastructure.sh" --environment "$ENVIRONMENT"
        
        # 3. Deploy S3 and basic infrastructure
        log_info "Step 3/7: Deploying storage infrastructure"
        "$DEPLOY_DIR/scripts/deploy-storage.sh" --environment "$ENVIRONMENT" --profile "$AWS_PROFILE"
        
        # 4. Initialize database
        log_info "Step 4/7: Initializing database"
        "$DEPLOY_DIR/scripts/deploy-database.sh" --environment "$ENVIRONMENT" --profile "$AWS_PROFILE"
        
        # 5. Deploy authentication
        log_info "Step 5/7: Deploying authentication services"
        "$DEPLOY_DIR/scripts/deploy-auth.sh" --environment "$ENVIRONMENT" --profile "$AWS_PROFILE"
        
        # 6. Deploy API and Lambda
        log_info "Step 6/7: Deploying API services"
        "$DEPLOY_DIR/scripts/deploy-api.sh" --environment "$ENVIRONMENT" --profile "$AWS_PROFILE"
        
        # 7. Deploy monitoring and notifications
        log_info "Step 7/7: Deploying monitoring and notifications"
        "$DEPLOY_DIR/scripts/deploy-monitoring.sh" --environment "$ENVIRONMENT" --profile "$AWS_PROFILE"
        
        # 8. Run post-deployment verification
        log_info "Running post-deployment verification"
        "$DEPLOY_DIR/scripts/verify-deployment.sh" --environment "$ENVIRONMENT" --profile "$AWS_PROFILE"
    fi
}

# Generate deployment summary
generate_summary() {
    local deployment_info_file="$PROJECT_ROOT/tmp/deployment-info-$ENVIRONMENT.json"
    local outputs_dir="$PROJECT_ROOT/tmp/outputs"
    
    mkdir -p "$(dirname "$deployment_info_file")" "$outputs_dir"
    
    # Create deployment summary
    cat > "$deployment_info_file" << EOF
{
  "deployment": {
    "environment": "$ENVIRONMENT",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "action": "$([ "$DESTROY_MODE" = true ] && echo "destroy" || echo "deploy")",
    "aws_account": "$AWS_ACCOUNT_ID",
    "aws_region": "$AWS_REGION",
    "aws_profile": "$AWS_PROFILE",
    "git_commit": "$(git rev-parse HEAD 2>/dev/null || echo "unknown")",
    "deployed_by": "$(whoami)",
    "script_version": "1.0.0"
  },
  "status": "$([ "$DESTROY_MODE" = true ] && echo "destroyed" || echo "deployed")"
}
EOF
    
    if [[ "$DESTROY_MODE" = false ]]; then
        # Get stack outputs
        local api_url=""
        local cognito_pool_id=""
        local s3_bucket=""
        
        # Try to get outputs from CloudFormation
        api_url=$(aws cloudformation describe-stacks \
            --stack-name "Echoes-Api-$ENVIRONMENT" \
            --profile "$AWS_PROFILE" \
            --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
            --output text 2>/dev/null || echo "")
            
        cognito_pool_id=$(aws cloudformation describe-stacks \
            --stack-name "Echoes-Auth-$ENVIRONMENT" \
            --profile "$AWS_PROFILE" \
            --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
            --output text 2>/dev/null || echo "")
            
        s3_bucket=$(aws cloudformation describe-stacks \
            --stack-name "Echoes-Storage-$ENVIRONMENT" \
            --profile "$AWS_PROFILE" \
            --query 'Stacks[0].Outputs[?OutputKey==`AudioBucketName`].OutputValue' \
            --output text 2>/dev/null || echo "")
        
        # Add resources to deployment info
        jq --arg api_url "$api_url" \
           --arg cognito_pool_id "$cognito_pool_id" \
           --arg s3_bucket "$s3_bucket" \
           '.resources = {
               "api_url": $api_url,
               "cognito_user_pool_id": $cognito_pool_id,
               "s3_bucket": $s3_bucket
           }' "$deployment_info_file" > "$deployment_info_file.tmp" && \
           mv "$deployment_info_file.tmp" "$deployment_info_file"
    fi
    
    log_success "Deployment summary saved to: $deployment_info_file"
}

# Print final status
print_final_status() {
    echo
    echo -e "${CYAN}=================================${NC}"
    
    if [[ "$DESTROY_MODE" = true ]]; then
        log_success "Infrastructure destroyed successfully!"
        echo -e "${BLUE}Environment '$ENVIRONMENT' has been completely removed.${NC}"
    else
        log_success "Deployment completed successfully!"
        echo -e "${BLUE}Environment '$ENVIRONMENT' is ready to use.${NC}"
        echo
        echo -e "${CYAN}📋 Deployment Summary:${NC}"
        
        # Show key resources
        local deployment_info_file="$PROJECT_ROOT/tmp/deployment-info-$ENVIRONMENT.json"
        if [[ -f "$deployment_info_file" ]] && command -v jq &> /dev/null; then
            local api_url
            local cognito_pool_id
            local s3_bucket
            
            api_url=$(jq -r '.resources.api_url // "Not available"' "$deployment_info_file")
            cognito_pool_id=$(jq -r '.resources.cognito_user_pool_id // "Not available"' "$deployment_info_file")
            s3_bucket=$(jq -r '.resources.s3_bucket // "Not available"' "$deployment_info_file")
            
            echo "  🔗 API Endpoint: $api_url"
            echo "  👤 Cognito User Pool: $cognito_pool_id"
            echo "  🗄️  S3 Bucket: $s3_bucket"
        fi
        
        echo
        echo -e "${CYAN}🚀 Next Steps:${NC}"
        echo "  1. Test API health: curl \$API_URL/health"
        echo "  2. Deploy frontend: ./deploy/scripts/deploy-frontend.sh -e $ENVIRONMENT"
        echo "  3. Run integration tests: ./deploy/scripts/run-tests.sh -e $ENVIRONMENT"
        echo "  4. View logs: ./deploy/scripts/view-logs.sh -e $ENVIRONMENT"
    fi
    
    echo -e "${CYAN}=================================${NC}"
}

# Main execution
main() {
    print_banner
    validate_environment
    check_prerequisites
    get_aws_info
    confirm_deployment
    
    local start_time
    start_time=$(date +%s)
    
    # Run deployment with error handling
    if run_deployment; then
        generate_summary
        print_final_status
        
        local end_time duration
        end_time=$(date +%s)
        duration=$((end_time - start_time))
        
        log_success "Total deployment time: ${duration}s"
    else
        local exit_code=$?
        log_error "Deployment failed with exit code: $exit_code"
        
        # Try to run rollback if deployment failed (not for destroy mode)
        if [[ "$DESTROY_MODE" = false ]] && [[ -f "$DEPLOY_DIR/scripts/rollback.sh" ]]; then
            log_warning "Attempting automatic rollback..."
            "$DEPLOY_DIR/scripts/rollback.sh" --environment "$ENVIRONMENT" --profile "$AWS_PROFILE" || true
        fi
        
        exit $exit_code
    fi
}

# Run main function
main "$@"