#!/bin/bash

# Echoes FastAPI Lambda Deployment Script
# Deploys the FastAPI backend to AWS Lambda using SAM CLI

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
STACK_NAME=""
PROFILE=""
CONFIRM="true"
BUILD_ONLY="false"
GUIDED="false"

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

Deploy Echoes FastAPI backend to AWS Lambda using SAM CLI

OPTIONS:
    -e, --environment ENV    Environment to deploy to (dev, staging, prod) [default: dev]
    -r, --region REGION      AWS region [default: us-east-1]
    -s, --stack-name NAME    CloudFormation stack name [default: echoes-{env}-backend]
    -p, --profile PROFILE    AWS profile to use [default: uses default profile]
    -b, --build-only         Only build the application, don't deploy
    -g, --guided             Run SAM deploy in guided mode
    -y, --yes                Skip confirmation prompts
    -h, --help               Show this help message

EXAMPLES:
    # Deploy to dev environment
    $0 -e dev

    # Deploy to production with specific profile
    $0 -e prod -p my-aws-profile

    # Build only without deploying
    $0 -b

    # Guided deployment (first time setup)
    $0 -g

PREREQUISITES:
    - AWS CLI configured with appropriate credentials
    - SAM CLI installed
    - Docker installed (for building Lambda packages)
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
        -s|--stack-name)
            STACK_NAME="$2"
            shift 2
            ;;
        -p|--profile)
            PROFILE="$2"
            shift 2
            ;;
        -b|--build-only)
            BUILD_ONLY="true"
            shift
            ;;
        -g|--guided)
            GUIDED="true"
            shift
            ;;
        -y|--yes)
            CONFIRM="false"
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

# Set default stack name if not provided
if [[ -z "$STACK_NAME" ]]; then
    STACK_NAME="echoes-${ENVIRONMENT}-backend"
fi

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_ROOT="$(cd "${BACKEND_DIR}/.." && pwd)"

print_info "Starting deployment process..."
print_info "Environment: $ENVIRONMENT"
print_info "Region: $REGION"
print_info "Stack Name: $STACK_NAME"
print_info "Backend Directory: $BACKEND_DIR"

# Change to backend directory
cd "$BACKEND_DIR"

# Check prerequisites
print_info "Checking prerequisites..."

if ! command -v sam &> /dev/null; then
    print_error "SAM CLI is not installed. Please install it first:"
    print_error "https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first:"
    print_error "https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v aws &> /dev/null; then
    print_error "AWS CLI is not installed. Please install it first:"
    print_error "https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html"
    exit 1
fi

# Test AWS credentials
print_info "Testing AWS credentials..."
AWS_CMD="aws"
if [[ -n "$PROFILE" ]]; then
    AWS_CMD="aws --profile $PROFILE"
    print_info "Using AWS profile: $PROFILE"
fi

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
print_success "AWS credentials verified (Account: $ACCOUNT_ID)"

# Load environment variables
ENV_FILE="${PROJECT_ROOT}/config/${ENVIRONMENT}.env"
if [[ -f "$ENV_FILE" ]]; then
    print_info "Loading environment variables from $ENV_FILE"
    set -a  # Automatically export all variables
    source "$ENV_FILE"
    set +a
else
    print_warning "Environment file not found: $ENV_FILE"
    print_warning "Using default configuration"
fi

# Prepare SAM build command
print_info "Building SAM application..."

SAM_BUILD_CMD="sam build"
if [[ -n "$PROFILE" ]]; then
    SAM_BUILD_CMD="$SAM_BUILD_CMD --profile $PROFILE"
fi

# Build the application
if ! $SAM_BUILD_CMD --use-container; then
    print_error "SAM build failed"
    exit 1
fi

print_success "SAM build completed successfully"

# Exit if build-only mode
if [[ "$BUILD_ONLY" == "true" ]]; then
    print_success "Build completed. Exiting as requested (--build-only)"
    exit 0
fi

# Prepare deployment parameters
DEPLOY_PARAMS=(
    "--region" "$REGION"
    "--stack-name" "$STACK_NAME"
    "--parameter-overrides"
    "Environment=$ENVIRONMENT"
    "--capabilities" "CAPABILITY_IAM"
    "--no-fail-on-empty-changeset"
)

if [[ -n "$PROFILE" ]]; then
    DEPLOY_PARAMS+=("--profile" "$PROFILE")
fi

# Add S3 bucket for deployment artifacts
S3_BUCKET="sam-deploy-${ACCOUNT_ID}-${REGION}"
DEPLOY_PARAMS+=("--s3-bucket" "$S3_BUCKET")

# Create S3 bucket if it doesn't exist
print_info "Ensuring S3 bucket exists for deployment artifacts: $S3_BUCKET"
if ! $AWS_CMD s3api head-bucket --bucket "$S3_BUCKET" 2>/dev/null; then
    print_info "Creating S3 bucket: $S3_BUCKET"
    if [[ "$REGION" == "us-east-1" ]]; then
        $AWS_CMD s3api create-bucket --bucket "$S3_BUCKET" --region "$REGION"
    else
        $AWS_CMD s3api create-bucket --bucket "$S3_BUCKET" --region "$REGION" \
            --create-bucket-configuration LocationConstraint="$REGION"
    fi
    
    # Enable versioning
    $AWS_CMD s3api put-bucket-versioning --bucket "$S3_BUCKET" \
        --versioning-configuration Status=Enabled
fi

# Guided deployment for first-time setup
if [[ "$GUIDED" == "true" ]]; then
    print_info "Running guided deployment..."
    sam deploy --guided "${DEPLOY_PARAMS[@]}"
    exit 0
fi

# Confirmation before deployment
if [[ "$CONFIRM" == "true" ]]; then
    echo
    print_warning "About to deploy with the following configuration:"
    echo "  Environment: $ENVIRONMENT"
    echo "  Region: $REGION"
    echo "  Stack Name: $STACK_NAME"
    echo "  AWS Account: $ACCOUNT_ID"
    if [[ -n "$PROFILE" ]]; then
        echo "  AWS Profile: $PROFILE"
    fi
    echo
    read -p "Continue with deployment? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Deployment cancelled by user"
        exit 0
    fi
fi

# Deploy the application
print_info "Deploying SAM application..."
print_info "This may take several minutes..."

if sam deploy "${DEPLOY_PARAMS[@]}"; then
    print_success "Deployment completed successfully!"
    
    # Get stack outputs
    print_info "Retrieving stack outputs..."
    
    OUTPUTS_CMD="$AWS_CMD cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query 'Stacks[0].Outputs'"
    OUTPUTS=$($OUTPUTS_CMD 2>/dev/null || echo "[]")
    
    if [[ "$OUTPUTS" != "[]" ]]; then
        echo
        print_success "Stack Outputs:"
        echo "$OUTPUTS" | python3 -m json.tool
    fi
    
    # Try to get API URL
    API_URL_CMD="$AWS_CMD cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query 'Stacks[0].Outputs[?OutputKey==\`ApiUrl\`].OutputValue' --output text"
    API_URL=$($API_URL_CMD 2>/dev/null || echo "")
    
    if [[ -n "$API_URL" && "$API_URL" != "None" ]]; then
        echo
        print_success "API Endpoint: $API_URL"
        print_info "Health check: $API_URL/health"
        print_info "API docs: $API_URL/docs"
    fi
    
    echo
    print_success "Deployment completed successfully!"
    print_info "Stack Name: $STACK_NAME"
    print_info "Region: $REGION"
    
else
    print_error "Deployment failed"
    exit 1
fi