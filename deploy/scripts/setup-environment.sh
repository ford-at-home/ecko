#!/bin/bash

# Environment Setup Script for Echoes Backend
# Prepares environment configuration, validates settings, and sets up deployment prerequisites

set -euo pipefail

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

# Script configuration
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
readonly DEPLOY_DIR="$PROJECT_ROOT/deploy"

# Default values
ENVIRONMENT="dev"
AWS_PROFILE="${AWS_PROFILE:-default}"
FORCE_UPDATE=false

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
        -f|--force)
            FORCE_UPDATE=true
            shift
            ;;
        -h|--help)
            cat << EOF
Environment Setup Script

Usage: $0 [options]

Options:
  -e, --environment <env>  Environment to setup (dev, staging, prod)
  -p, --profile <profile>  AWS profile to use
  -f, --force             Force update existing configuration
  -h, --help              Show this help message

This script:
  1. Validates environment configuration
  2. Generates deployment-specific configs
  3. Sets up AWS account-specific values
  4. Prepares CDK context files
  5. Validates all prerequisites
EOF
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}" >&2
            exit 1
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

# Get AWS account information
get_aws_info() {
    log_info "Getting AWS account information"
    
    if ! AWS_ACCOUNT_ID=$(aws sts get-caller-identity --profile "$AWS_PROFILE" --query Account --output text 2>/dev/null); then
        log_error "Failed to get AWS account ID. Check your AWS profile: $AWS_PROFILE"
        exit 1
    fi
    
    if ! AWS_REGION=$(aws configure get region --profile "$AWS_PROFILE" 2>/dev/null); then
        AWS_REGION="us-east-1"
        log_warning "No default region configured, using: $AWS_REGION"
    fi
    
    export AWS_ACCOUNT_ID AWS_REGION
    log_success "AWS Account: $AWS_ACCOUNT_ID, Region: $AWS_REGION"
}

# Validate environment configuration
validate_environment() {
    log_info "Validating environment: $ENVIRONMENT"
    
    if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
        log_error "Invalid environment: $ENVIRONMENT"
        exit 1
    fi
    
    # Check if environment config exists
    local env_config_file="$PROJECT_ROOT/config/${ENVIRONMENT}.json"
    if [[ ! -f "$env_config_file" ]]; then
        log_error "Environment configuration not found: $env_config_file"
        exit 1
    fi
    
    # Validate JSON syntax
    if ! jq empty "$env_config_file" 2>/dev/null; then
        log_error "Invalid JSON in environment config: $env_config_file"
        exit 1
    fi
    
    log_success "Environment configuration validated"
}

# Generate deployment configuration
generate_deployment_config() {
    log_info "Generating deployment configuration"
    
    local config_dir="$DEPLOY_DIR/configs/$ENVIRONMENT"
    mkdir -p "$config_dir"
    
    local deployment_config="$config_dir/deployment.json"
    local env_config="$PROJECT_ROOT/config/${ENVIRONMENT}.json"
    
    # Generate unique resource names
    local stack_suffix="${ENVIRONMENT}-${AWS_ACCOUNT_ID:0:8}"
    local bucket_name="echoes-audio-${ENVIRONMENT}-${AWS_ACCOUNT_ID}"
    local table_name="EchoesTable-${ENVIRONMENT}"
    local user_pool_name="echoes-users-${ENVIRONMENT}"
    local api_name="echoes-api-${ENVIRONMENT}"
    
    # Create deployment configuration
    cat > "$deployment_config" << EOF
{
  "environment": "$ENVIRONMENT",
  "aws": {
    "accountId": "$AWS_ACCOUNT_ID",
    "region": "$AWS_REGION",
    "profile": "$AWS_PROFILE"
  },
  "resources": {
    "s3": {
      "bucketName": "$bucket_name",
      "bucketArn": "arn:aws:s3:::$bucket_name"
    },
    "dynamodb": {
      "tableName": "$table_name",
      "tableArn": "arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/$table_name"
    },
    "cognito": {
      "userPoolName": "$user_pool_name",
      "userPoolId": "",
      "userPoolClientId": "",
      "identityPoolId": ""
    },
    "apiGateway": {
      "apiName": "$api_name",
      "apiId": "",
      "apiUrl": ""
    },
    "lambda": {
      "functionName": "echoes-api-${ENVIRONMENT}",
      "functionArn": ""
    }
  },
  "tags": {
    "Environment": "$ENVIRONMENT",
    "Project": "Echoes",
    "ManagedBy": "EchoesDeployment",
    "Account": "$AWS_ACCOUNT_ID",
    "Region": "$AWS_REGION"
  },
  "generated": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
    
    # Merge with environment-specific configuration
    if command -v jq &> /dev/null; then
        local temp_config="$deployment_config.tmp"
        jq --slurpfile env_settings "$env_config" '. + {"settings": $env_settings[0].settings}' "$deployment_config" > "$temp_config"
        mv "$temp_config" "$deployment_config"
    fi
    
    log_success "Deployment configuration generated: $deployment_config"
}

# Setup CDK context
setup_cdk_context() {
    log_info "Setting up CDK context"
    
    local cdk_dir="$PROJECT_ROOT/cdk"
    local context_file="$cdk_dir/cdk.context.json"
    
    # Ensure CDK directory exists
    if [[ ! -d "$cdk_dir" ]]; then
        log_error "CDK directory not found: $cdk_dir"
        exit 1
    fi
    
    # Create or update CDK context
    local context_data='{
  "acknowledged-issue-numbers": [20901, 19836, 20779, 16603],
  "availability-zones:account='$AWS_ACCOUNT_ID':region='$AWS_REGION'": [
    "'$AWS_REGION'a",
    "'$AWS_REGION'b",
    "'$AWS_REGION'c"
  ],
  "hosted-zone:account='$AWS_ACCOUNT_ID':domainName=example.com:region='$AWS_REGION'": {
    "Id": "/hostedzone/Z123456789",
    "Name": "example.com."
  },
  "environment": "'$ENVIRONMENT'",
  "awsAccountId": "'$AWS_ACCOUNT_ID'",
  "awsRegion": "'$AWS_REGION'"
}'
    
    echo "$context_data" > "$context_file"
    log_success "CDK context configured: $context_file"
}

# Generate environment variables file
generate_env_file() {
    log_info "Generating environment variables file"
    
    local env_dir="$PROJECT_ROOT/environments/$ENVIRONMENT"
    mkdir -p "$env_dir"
    local env_file="$env_dir/.env.infrastructure"
    
    # Create infrastructure environment file
    cat > "$env_file" << EOF
# Generated infrastructure environment file for $ENVIRONMENT
# Generated on: $(date -u +%Y-%m-%dT%H:%M:%SZ)

# Environment Configuration
ENVIRONMENT=$ENVIRONMENT
AWS_ACCOUNT_ID=$AWS_ACCOUNT_ID
AWS_REGION=$AWS_REGION
AWS_PROFILE=$AWS_PROFILE

# Resource Names
S3_BUCKET_NAME=echoes-audio-${ENVIRONMENT}-${AWS_ACCOUNT_ID}
DYNAMODB_TABLE_NAME=EchoesTable-${ENVIRONMENT}
COGNITO_USER_POOL_NAME=echoes-users-${ENVIRONMENT}
API_GATEWAY_NAME=echoes-api-${ENVIRONMENT}
LAMBDA_FUNCTION_NAME=echoes-api-${ENVIRONMENT}

# Stack Names
STORAGE_STACK_NAME=Echoes-Storage-${ENVIRONMENT}
AUTH_STACK_NAME=Echoes-Auth-${ENVIRONMENT}
API_STACK_NAME=Echoes-Api-${ENVIRONMENT}
NOTIF_STACK_NAME=Echoes-Notif-${ENVIRONMENT}

# CDK Configuration
CDK_QUALIFIER=${ENVIRONMENT}echoes
CDK_BOOTSTRAP_BUCKET_NAME=cdk-${AWS_ACCOUNT_ID}-${AWS_REGION}-${ENVIRONMENT}

# Deployment Configuration
DEPLOYMENT_TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
DEPLOYMENT_USER=$(whoami)
GIT_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
EOF
    
    log_success "Environment file generated: $env_file"
}

# Validate CDK setup
validate_cdk_setup() {
    log_info "Validating CDK setup"
    
    local cdk_dir="$PROJECT_ROOT/cdk"
    
    # Check CDK directory structure
    if [[ ! -f "$cdk_dir/package.json" ]]; then
        log_error "CDK package.json not found"
        exit 1
    fi
    
    if [[ ! -f "$cdk_dir/cdk.json" ]]; then
        log_error "CDK cdk.json not found"
        exit 1
    fi
    
    # Install CDK dependencies if needed
    if [[ ! -d "$cdk_dir/node_modules" ]] || [[ "$FORCE_UPDATE" = true ]]; then
        log_info "Installing CDK dependencies"
        (cd "$cdk_dir" && npm ci)
    fi
    
    # Build CDK TypeScript
    log_info "Building CDK TypeScript"
    (cd "$cdk_dir" && npm run build)
    
    log_success "CDK setup validated"
}

# Check backend setup
validate_backend_setup() {
    log_info "Validating backend setup"
    
    local backend_dir="$PROJECT_ROOT/backend"
    
    if [[ ! -f "$backend_dir/requirements.txt" ]]; then
        log_error "Backend requirements.txt not found"
        exit 1
    fi
    
    if [[ ! -f "$backend_dir/simple_lambda.py" ]] && [[ ! -f "$backend_dir/lambda_handler.py" ]]; then
        log_error "Lambda handler not found"
        exit 1
    fi
    
    log_success "Backend setup validated"
}

# Create temporary directories
create_temp_directories() {
    log_info "Creating temporary directories"
    
    local temp_dirs=(
        "$PROJECT_ROOT/tmp"
        "$PROJECT_ROOT/tmp/outputs"
        "$PROJECT_ROOT/tmp/logs"
        "$PROJECT_ROOT/tmp/backups"
        "$DEPLOY_DIR/configs/$ENVIRONMENT"
        "$DEPLOY_DIR/templates/$ENVIRONMENT"
    )
    
    for dir in "${temp_dirs[@]}"; do
        mkdir -p "$dir"
    done
    
    log_success "Temporary directories created"
}

# Generate deployment summary
generate_summary() {
    log_info "Generating setup summary"
    
    local summary_file="$PROJECT_ROOT/tmp/setup-summary-$ENVIRONMENT.json"
    
    cat > "$summary_file" << EOF
{
  "setup": {
    "environment": "$ENVIRONMENT",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "aws_account": "$AWS_ACCOUNT_ID",
    "aws_region": "$AWS_REGION",
    "aws_profile": "$AWS_PROFILE"
  },
  "resources": {
    "s3_bucket": "echoes-audio-${ENVIRONMENT}-${AWS_ACCOUNT_ID}",
    "dynamodb_table": "EchoesTable-${ENVIRONMENT}",
    "cognito_user_pool": "echoes-users-${ENVIRONMENT}",
    "api_gateway": "echoes-api-${ENVIRONMENT}",
    "lambda_function": "echoes-api-${ENVIRONMENT}"
  },
  "files_generated": [
    "deploy/configs/$ENVIRONMENT/deployment.json",
    "environments/$ENVIRONMENT/.env.infrastructure",
    "cdk/cdk.context.json"
  ],
  "status": "completed"
}
EOF
    
    log_success "Setup summary saved: $summary_file"
}

# Main execution
main() {
    echo -e "${BLUE}🔧 Setting up environment: $ENVIRONMENT${NC}"
    echo "================================="
    
    get_aws_info
    validate_environment
    create_temp_directories
    generate_deployment_config
    setup_cdk_context
    generate_env_file
    validate_cdk_setup
    validate_backend_setup
    generate_summary
    
    echo
    log_success "Environment setup completed successfully!"
    echo -e "${BLUE}Environment '$ENVIRONMENT' is ready for deployment.${NC}"
    echo
    echo -e "${BLUE}Next step: Run the infrastructure deployment${NC}"
}

# Run main function
main "$@"