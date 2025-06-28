#!/bin/bash

# Echoes Cleanup Script
# Manages cleanup of AWS resources and local build artifacts

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT=""
REGION="us-east-1"
PROFILE=""
LOCAL_ONLY="false"
FORCE="false"
DRY_RUN="false"

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

print_dry_run() {
    echo -e "${YELLOW}[DRY RUN]${NC} Would execute: $1"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Clean up Echoes deployment resources and build artifacts

OPTIONS:
    -e, --environment ENV    Environment to clean up (dev, staging, prod)
    -r, --region REGION      AWS region [default: us-east-1]
    -p, --profile PROFILE    AWS profile to use [default: uses default profile]
    -l, --local-only         Only clean local build artifacts, not AWS resources
    -f, --force              Skip confirmation prompts
    -d, --dry-run            Show what would be deleted without actually deleting
    -h, --help               Show this help message

EXAMPLES:
    # Clean up local build artifacts only
    $0 --local-only

    # Clean up dev environment (with confirmation)
    $0 -e dev

    # Dry run for production cleanup
    $0 -e prod --dry-run

    # Force cleanup without confirmation
    $0 -e dev --force

WARNING:
    This script will DELETE AWS resources including:
    - CloudFormation stack
    - S3 buckets and all contents
    - DynamoDB tables and all data
    - Lambda functions
    - API Gateway resources
    - Cognito User Pools
    
    Use with caution, especially in production environments!

WHAT THIS SCRIPT CLEANS:
    Local artifacts:
    - SAM build directories
    - Python cache files
    - Temporary files
    
    AWS resources (when -e specified):
    - CloudFormation stack and all resources
    - S3 buckets (including deployment bucket)
    - CloudWatch logs
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
        -l|--local-only)
            LOCAL_ONLY="true"
            shift
            ;;
        -f|--force)
            FORCE="true"
            shift
            ;;
        -d|--dry-run)
            DRY_RUN="true"
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

# Get script directory and project paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_ROOT="$(cd "${BACKEND_DIR}/.." && pwd)"

print_info "Starting cleanup process..."

# Function to execute or dry run
execute_or_dry_run() {
    local command="$1"
    if [[ "$DRY_RUN" == "true" ]]; then
        print_dry_run "$command"
    else
        eval "$command"
    fi
}

# Clean local build artifacts
clean_local_artifacts() {
    print_info "Cleaning local build artifacts..."
    
    cd "$BACKEND_DIR"
    
    # SAM build directories
    if [[ -d ".aws-sam" ]]; then
        print_info "Removing SAM build directory..."
        execute_or_dry_run "rm -rf .aws-sam/"
    fi
    
    # Python cache files
    print_info "Cleaning Python cache files..."
    execute_or_dry_run "find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true"
    execute_or_dry_run "find . -name '*.pyc' -delete 2>/dev/null || true"
    execute_or_dry_run "find . -name '*.pyo' -delete 2>/dev/null || true"
    
    # Temporary files
    execute_or_dry_run "find . -name '*.tmp' -delete 2>/dev/null || true"
    execute_or_dry_run "find . -name '*.temp' -delete 2>/dev/null || true"
    
    # Log files
    execute_or_dry_run "find . -name '*.log' -delete 2>/dev/null || true"
    
    # Coverage reports
    execute_or_dry_run "rm -rf htmlcov/ 2>/dev/null || true"
    execute_or_dry_run "rm -f .coverage 2>/dev/null || true"
    
    # Virtual environments (if any)
    execute_or_dry_run "rm -rf venv/ 2>/dev/null || true"
    execute_or_dry_run "rm -rf .venv/ 2>/dev/null || true"
    
    print_success "Local build artifacts cleaned"
}

# Clean AWS resources
clean_aws_resources() {
    local env="$1"
    
    # Validate environment
    if [[ ! "$env" =~ ^(dev|staging|prod)$ ]]; then
        print_error "Invalid environment: $env. Must be dev, staging, or prod"
        exit 1
    fi
    
    print_info "Cleaning AWS resources for environment: $env"
    
    # Setup AWS command with profile if specified
    AWS_CMD="aws"
    if [[ -n "$PROFILE" ]]; then
        AWS_CMD="aws --profile $PROFILE"
        print_info "Using AWS profile: $PROFILE"
    fi
    
    # Validate AWS credentials
    if ! $AWS_CMD sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials not configured or invalid"
        exit 1
    fi
    
    ACCOUNT_ID=$($AWS_CMD sts get-caller-identity --query Account --output text)
    print_info "AWS Account: $ACCOUNT_ID"
    
    # Generate resource names
    STACK_NAME="echoes-${env}-backend"
    S3_BUCKET="echoes-audio-${env}-${ACCOUNT_ID}"
    DEPLOY_BUCKET="sam-deploy-${ACCOUNT_ID}-${REGION}"
    LOG_GROUP="/aws/lambda/echoes-${env}-api"
    
    print_info "Resources to clean:"
    print_info "  Stack: $STACK_NAME"
    print_info "  S3 Bucket: $S3_BUCKET"
    print_info "  Deploy Bucket: $DEPLOY_BUCKET"
    print_info "  Log Group: $LOG_GROUP"
    
    # Confirmation if not forced or dry run
    if [[ "$FORCE" != "true" && "$DRY_RUN" != "true" ]]; then
        echo
        print_warning "WARNING: This will DELETE all AWS resources for environment '$env'"
        print_warning "This action cannot be undone!"
        echo
        read -p "Are you sure you want to continue? Type 'DELETE' to confirm: " -r
        echo
        if [[ "$REPLY" != "DELETE" ]]; then
            print_info "Cleanup cancelled by user"
            exit 0
        fi
    fi
    
    # Check if CloudFormation stack exists
    if $AWS_CMD cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" &> /dev/null; then
        STACK_STATUS=$($AWS_CMD cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" --query 'Stacks[0].StackStatus' --output text)
        print_info "Found CloudFormation stack: $STACK_NAME (Status: $STACK_STATUS)"
        
        # Delete CloudFormation stack
        print_info "Deleting CloudFormation stack: $STACK_NAME"
        execute_or_dry_run "$AWS_CMD cloudformation delete-stack --stack-name $STACK_NAME --region $REGION"
        
        if [[ "$DRY_RUN" != "true" ]]; then
            print_info "Waiting for stack deletion to complete..."
            if ! $AWS_CMD cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" --region "$REGION"; then
                print_error "Stack deletion failed or timed out"
                print_info "Check the CloudFormation console for details"
            else
                print_success "CloudFormation stack deleted successfully"
            fi
        fi
    else
        print_info "CloudFormation stack not found: $STACK_NAME"
    fi
    
    # Clean up S3 buckets
    if $AWS_CMD s3api head-bucket --bucket "$S3_BUCKET" --region "$REGION" &> /dev/null; then
        print_info "Cleaning S3 bucket: $S3_BUCKET"
        execute_or_dry_run "$AWS_CMD s3 rm s3://$S3_BUCKET --recursive"
        execute_or_dry_run "$AWS_CMD s3api delete-bucket --bucket $S3_BUCKET --region $REGION"
    else
        print_info "S3 bucket not found: $S3_BUCKET"
    fi
    
    # Clean up deployment bucket (only if it's empty and we're in dry run or force mode)
    if $AWS_CMD s3api head-bucket --bucket "$DEPLOY_BUCKET" --region "$REGION" &> /dev/null; then
        print_info "Deployment bucket exists: $DEPLOY_BUCKET"
        if [[ "$FORCE" == "true" ]]; then
            print_warning "Force mode: cleaning deployment bucket"
            execute_or_dry_run "$AWS_CMD s3 rm s3://$DEPLOY_BUCKET --recursive"
        else
            print_info "Deployment bucket preserved (contains artifacts for other environments)"
            print_info "Use --force to delete deployment bucket"
        fi
    fi
    
    # Clean up CloudWatch logs
    if $AWS_CMD logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" --region "$REGION" &> /dev/null; then
        print_info "Deleting CloudWatch log group: $LOG_GROUP"
        execute_or_dry_run "$AWS_CMD logs delete-log-group --log-group-name $LOG_GROUP --region $REGION"
    else
        print_info "CloudWatch log group not found: $LOG_GROUP"
    fi
    
    print_success "AWS resource cleanup completed for environment: $env"
}

# Main execution
clean_local_artifacts

if [[ "$LOCAL_ONLY" != "true" && -n "$ENVIRONMENT" ]]; then
    clean_aws_resources "$ENVIRONMENT"
elif [[ "$LOCAL_ONLY" != "true" && -z "$ENVIRONMENT" ]]; then
    print_error "Environment (-e) is required for AWS resource cleanup"
    print_info "Use --local-only to clean only local artifacts"
    exit 1
fi

echo
if [[ "$DRY_RUN" == "true" ]]; then
    print_info "Dry run completed. No resources were actually deleted."
else
    print_success "Cleanup completed successfully!"
fi

if [[ -n "$ENVIRONMENT" && "$LOCAL_ONLY" != "true" ]]; then
    echo
    print_info "Environment '$ENVIRONMENT' has been cleaned up."
    print_info "To redeploy, run:"
    print_info "  ./scripts/env-setup.sh -e $ENVIRONMENT"
    print_info "  ./scripts/build.sh"
    print_info "  ./scripts/deploy.sh -e $ENVIRONMENT"
fi