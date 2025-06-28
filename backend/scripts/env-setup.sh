#!/bin/bash

# Echoes Environment Setup Script
# Sets up environment-specific configuration and validates AWS resources

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="dev"
REGION="us-east-1"
PROFILE=""
CREATE_RESOURCES="false"

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Set up and validate environment configuration for Echoes deployment

OPTIONS:
    -e, --environment ENV    Environment to set up (dev, staging, prod) [default: dev]
    -r, --region REGION      AWS region [default: us-east-1]
    -p, --profile PROFILE    AWS profile to use [default: uses default profile]
    -c, --create             Create missing AWS resources
    -h, --help               Show this help message

EXAMPLES:
    # Setup dev environment
    $0 -e dev

    # Setup production with specific profile
    $0 -e prod -p production-profile

    # Setup and create missing resources
    $0 -e dev -c

WHAT THIS SCRIPT DOES:
    1. Validates AWS credentials and permissions
    2. Checks for required AWS resources
    3. Creates environment configuration files
    4. Validates environment variables
    5. Optionally creates missing resources
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -p|--profile)
            PROFILE="$2"
            shift 2
            ;;
        -c|--create)
            CREATE_RESOURCES="true"
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    print_error "Invalid environment: $ENVIRONMENT. Must be dev, staging, or prod"
    exit 1
fi

# Get script directory and project paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_ROOT="$(cd "${BACKEND_DIR}/.." && pwd)"
CONFIG_DIR="${PROJECT_ROOT}/config"

print_info "Setting up environment: $ENVIRONMENT"
print_info "Region: $REGION"
print_info "Config Directory: $CONFIG_DIR"

# Ensure config directory exists
mkdir -p "$CONFIG_DIR"

# Setup AWS command with profile if specified
AWS_CMD="aws"
if [[ -n "$PROFILE" ]]; then
    AWS_CMD="aws --profile $PROFILE"
    print_info "Using AWS profile: $PROFILE"
fi

# Validate AWS credentials
print_info "Validating AWS credentials..."

if ! $AWS_CMD sts get-caller-identity &> /dev/null; then
    print_error "AWS credentials not configured or invalid"
    if [[ -n "$PROFILE" ]]; then
        print_error "Check your AWS profile: $PROFILE"
    else
        print_error "Run 'aws configure' to set up credentials"
    fi
    exit 1
fi

ACCOUNT_ID=$($AWS_CMD sts get-caller-identity --query Account --output text)
USER_ARN=$($AWS_CMD sts get-caller-identity --query Arn --output text)

print_success "AWS credentials validated"
print_info "Account ID: $ACCOUNT_ID"
print_info "User/Role: $USER_ARN"

# Check required AWS permissions
print_info "Checking AWS permissions..."

REQUIRED_PERMISSIONS=(
    "lambda:CreateFunction"
    "lambda:UpdateFunctionCode"
    "lambda:GetFunction"
    "apigateway:GET"
    "apigateway:POST"
    "apigateway:PUT"
    "cloudformation:CreateStack"
    "cloudformation:UpdateStack"
    "cloudformation:DescribeStacks"
    "iam:CreateRole"
    "iam:AttachRolePolicy"
    "iam:PassRole"
    "s3:CreateBucket"
    "s3:PutObject"
    "s3:GetObject"
    "dynamodb:CreateTable"
    "dynamodb:DescribeTable"
)

# Test permissions by checking if we can list resources
PERMISSION_ERRORS=()

if ! $AWS_CMD lambda list-functions --region "$REGION" &> /dev/null; then
    PERMISSION_ERRORS+=("Lambda permissions")
fi

if ! $AWS_CMD apigateway get-rest-apis --region "$REGION" &> /dev/null; then
    PERMISSION_ERRORS+=("API Gateway permissions")
fi

if ! $AWS_CMD cloudformation list-stacks --region "$REGION" &> /dev/null; then
    PERMISSION_ERRORS+=("CloudFormation permissions")
fi

if ! $AWS_CMD s3 ls &> /dev/null; then
    PERMISSION_ERRORS+=("S3 permissions")
fi

if ! $AWS_CMD dynamodb list-tables --region "$REGION" &> /dev/null; then
    PERMISSION_ERRORS+=("DynamoDB permissions")
fi

if [[ ${#PERMISSION_ERRORS[@]} -gt 0 ]]; then
    print_warning "Some permissions may be missing:"
    for error in "${PERMISSION_ERRORS[@]}"; do
        print_warning "  - $error"
    done
    print_warning "Deployment may fail if these permissions are not available"
else
    print_success "AWS permissions validated"
fi

# Generate resource names
STACK_NAME="echoes-${ENVIRONMENT}-backend"
S3_BUCKET="echoes-audio-${ENVIRONMENT}-${ACCOUNT_ID}"
DYNAMODB_TABLE="EchoesTable-${ENVIRONMENT}"
COGNITO_USER_POOL="echoes-${ENVIRONMENT}-users"

print_info "Resource names:"
print_info "  Stack: $STACK_NAME"
print_info "  S3 Bucket: $S3_BUCKET"
print_info "  DynamoDB Table: $DYNAMODB_TABLE"
print_info "  Cognito User Pool: $COGNITO_USER_POOL"

# Check existing resources
print_info "Checking existing AWS resources..."

# Check CloudFormation stack
STACK_EXISTS="false"
if $AWS_CMD cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" &> /dev/null; then
    STACK_EXISTS="true"
    STACK_STATUS=$($AWS_CMD cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" --query 'Stacks[0].StackStatus' --output text)
    print_info "CloudFormation stack exists: $STACK_NAME (Status: $STACK_STATUS)"
else
    print_info "CloudFormation stack does not exist: $STACK_NAME"
fi

# Check S3 bucket
BUCKET_EXISTS="false"
if $AWS_CMD s3api head-bucket --bucket "$S3_BUCKET" --region "$REGION" &> /dev/null; then
    BUCKET_EXISTS="true"
    print_info "S3 bucket exists: $S3_BUCKET"
else
    print_info "S3 bucket does not exist: $S3_BUCKET"
fi

# Check DynamoDB table
TABLE_EXISTS="false"
if $AWS_CMD dynamodb describe-table --table-name "$DYNAMODB_TABLE" --region "$REGION" &> /dev/null; then
    TABLE_EXISTS="true"
    TABLE_STATUS=$($AWS_CMD dynamodb describe-table --table-name "$DYNAMODB_TABLE" --region "$REGION" --query 'Table.TableStatus' --output text)
    print_info "DynamoDB table exists: $DYNAMODB_TABLE (Status: $TABLE_STATUS)"
else
    print_info "DynamoDB table does not exist: $DYNAMODB_TABLE"
fi

# Generate environment configuration
print_info "Generating environment configuration..."

ENV_FILE="${CONFIG_DIR}/${ENVIRONMENT}.env"

cat > "$ENV_FILE" << EOF
# Echoes Environment Configuration - $ENVIRONMENT
# Generated on $(date)

# Environment
ENVIRONMENT=$ENVIRONMENT
DEBUG=$([ "$ENVIRONMENT" == "prod" ] && echo "false" || echo "true")
LOG_LEVEL=$([ "$ENVIRONMENT" == "prod" ] && echo "INFO" || echo "DEBUG")

# AWS Configuration
AWS_REGION=$REGION
AWS_ACCOUNT_ID=$ACCOUNT_ID

# DynamoDB
DYNAMODB_TABLE_NAME=$DYNAMODB_TABLE

# S3
S3_BUCKET_NAME=$S3_BUCKET
S3_PRESIGNED_URL_EXPIRATION=3600

# API Gateway & CORS
CORS_ALLOW_ORIGINS=$([ "$ENVIRONMENT" == "prod" ] && echo "https://yourdomain.com" || echo "http://localhost:3000,http://127.0.0.1:3000")

# JWT Configuration
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=1440

# Audio Configuration
MAX_AUDIO_FILE_SIZE=10485760
ALLOWED_AUDIO_FORMATS=webm,wav,mp3,m4a,ogg

# Rate Limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# Cognito (will be populated after deployment)
COGNITO_USER_POOL_ID=
COGNITO_CLIENT_ID=
COGNITO_REGION=$REGION
EOF

print_success "Environment configuration created: $ENV_FILE"

# Create samconfig.toml for SAM CLI
SAMCONFIG_FILE="${BACKEND_DIR}/samconfig.toml"

cat > "$SAMCONFIG_FILE" << EOF
version = 0.1

[default]
[default.build]
[default.build.parameters]
use_container = true

[default.validate]
[default.validate.parameters]
lint = true

[default.deploy]
[default.deploy.parameters]
stack_name = "$STACK_NAME"
s3_bucket = "sam-deploy-${ACCOUNT_ID}-${REGION}"
region = "$REGION"
confirm_changeset = false
capabilities = "CAPABILITY_IAM"
parameter_overrides = "Environment=$ENVIRONMENT"
EOF

if [[ -n "$PROFILE" ]]; then
    echo "profile = \"$PROFILE\"" >> "$SAMCONFIG_FILE"
fi

print_success "SAM configuration created: $SAMCONFIG_FILE"

# Create resource creation script if requested
if [[ "$CREATE_RESOURCES" == "true" ]]; then
    print_info "Creating missing AWS resources..."
    
    # Create S3 bucket for deployment artifacts
    DEPLOY_BUCKET="sam-deploy-${ACCOUNT_ID}-${REGION}"
    if ! $AWS_CMD s3api head-bucket --bucket "$DEPLOY_BUCKET" &> /dev/null; then
        print_info "Creating deployment S3 bucket: $DEPLOY_BUCKET"
        if [[ "$REGION" == "us-east-1" ]]; then
            $AWS_CMD s3api create-bucket --bucket "$DEPLOY_BUCKET" --region "$REGION"
        else
            $AWS_CMD s3api create-bucket --bucket "$DEPLOY_BUCKET" --region "$REGION" \
                --create-bucket-configuration LocationConstraint="$REGION"
        fi
        
        # Enable versioning
        $AWS_CMD s3api put-bucket-versioning --bucket "$DEPLOY_BUCKET" \
            --versioning-configuration Status=Enabled
        
        print_success "Deployment S3 bucket created: $DEPLOY_BUCKET"
    fi
fi

# Validate environment file
print_info "Validating environment configuration..."

if [[ -f "$ENV_FILE" ]]; then
    # Check for any missing required variables
    REQUIRED_VARS=(
        "ENVIRONMENT"
        "AWS_REGION"
        "DYNAMODB_TABLE_NAME"
        "S3_BUCKET_NAME"
    )
    
    MISSING_VARS=()
    for var in "${REQUIRED_VARS[@]}"; do
        if ! grep -q "^${var}=" "$ENV_FILE"; then
            MISSING_VARS+=("$var")
        fi
    done
    
    if [[ ${#MISSING_VARS[@]} -gt 0 ]]; then
        print_error "Missing required environment variables:"
        for var in "${MISSING_VARS[@]}"; do
            print_error "  - $var"
        done
        exit 1
    fi
    
    print_success "Environment configuration validated"
else
    print_error "Environment file not created: $ENV_FILE"
    exit 1
fi

# Summary
echo
print_success "Environment setup completed successfully!"
echo
print_info "Configuration Summary:"
print_info "  Environment: $ENVIRONMENT"
print_info "  Region: $REGION"
print_info "  AWS Account: $ACCOUNT_ID"
print_info "  Config File: $ENV_FILE"
print_info "  SAM Config: $SAMCONFIG_FILE"
echo
print_info "Next steps:"
print_info "  1. Review and customize the configuration in $ENV_FILE"
print_info "  2. Run ./scripts/build.sh to build the application"
print_info "  3. Run ./scripts/deploy.sh to deploy to AWS"
echo
if [[ "$STACK_EXISTS" == "false" ]]; then
    print_warning "First deployment detected. Consider using guided deployment:"
    print_warning "  ./scripts/deploy.sh -g"
fi