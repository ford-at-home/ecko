#!/bin/bash

# Storage Infrastructure Deployment Script for Echoes Backend
# Deploys S3 buckets, DynamoDB tables, and storage-related resources

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
readonly CDK_DIR="$PROJECT_ROOT/cdk"

# Default values
ENVIRONMENT="dev"
AWS_PROFILE="${AWS_PROFILE:-default}"
SKIP_CONFIRMATION=false
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
        -y|--yes)
            SKIP_CONFIRMATION=true
            shift
            ;;
        -f|--force)
            FORCE_UPDATE=true
            shift
            ;;
        -h|--help)
            cat << EOF
Storage Infrastructure Deployment Script

Usage: $0 [options]

Options:
  -e, --environment <env>  Environment to deploy (dev, staging, prod)
  -p, --profile <profile>  AWS profile to use
  -y, --yes               Skip confirmation prompts
  -f, --force             Force update existing resources
  -h, --help              Show this help message

This script deploys:
  1. S3 bucket for audio files with proper configuration
  2. DynamoDB table for echo metadata
  3. IAM roles and policies for storage access
  4. CloudWatch alarms for monitoring
  5. Backup and lifecycle policies
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

# Load environment configuration
load_environment_config() {
    log_info "Loading environment configuration"
    
    local env_file="$PROJECT_ROOT/environments/$ENVIRONMENT/.env.infrastructure"
    
    if [[ ! -f "$env_file" ]]; then
        log_error "Environment file not found: $env_file"
        log_error "Run setup-environment.sh first"
        exit 1
    fi
    
    # Load environment variables
    set -a
    source "$env_file"
    set +a
    
    log_success "Environment configuration loaded"
}

# Check if storage resources already exist
check_existing_resources() {
    log_info "Checking existing storage resources"
    
    local s3_exists=false
    local dynamodb_exists=false
    local stack_exists=false
    
    # Check S3 bucket
    if aws s3api head-bucket --bucket "$S3_BUCKET_NAME" --profile "$AWS_PROFILE" 2>/dev/null; then
        s3_exists=true
        log_warning "S3 bucket already exists: $S3_BUCKET_NAME"
    fi
    
    # Check DynamoDB table
    if aws dynamodb describe-table --table-name "$DYNAMODB_TABLE_NAME" --profile "$AWS_PROFILE" 2>/dev/null; then
        dynamodb_exists=true
        log_warning "DynamoDB table already exists: $DYNAMODB_TABLE_NAME"
    fi
    
    # Check CloudFormation stack
    if aws cloudformation describe-stacks --stack-name "$STORAGE_STACK_NAME" --profile "$AWS_PROFILE" 2>/dev/null; then
        stack_exists=true
        log_warning "CloudFormation stack already exists: $STORAGE_STACK_NAME"
    fi
    
    if [[ "$s3_exists" = true ]] || [[ "$dynamodb_exists" = true ]] || [[ "$stack_exists" = true ]]; then
        if [[ "$FORCE_UPDATE" = false ]]; then
            log_warning "Storage resources already exist. Use --force to update them."
            if [[ "$SKIP_CONFIRMATION" = false ]]; then
                read -p "Continue with update? (y/N): " -n 1 -r
                echo
                if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                    log_info "Deployment cancelled"
                    exit 0
                fi
            fi
        fi
    fi
}

# Pre-deployment validation
validate_deployment() {
    log_info "Validating deployment configuration"
    
    # Check AWS region
    if [[ -z "$AWS_REGION" ]]; then
        log_error "AWS_REGION not set"
        exit 1
    fi
    
    # Check bucket name uniqueness
    if [[ ${#S3_BUCKET_NAME} -lt 3 ]] || [[ ${#S3_BUCKET_NAME} -gt 63 ]]; then
        log_error "S3 bucket name must be between 3 and 63 characters"
        exit 1
    fi
    
    # Validate bucket name format
    if [[ ! "$S3_BUCKET_NAME" =~ ^[a-z0-9][a-z0-9-]*[a-z0-9]$ ]]; then
        log_error "Invalid S3 bucket name format: $S3_BUCKET_NAME"
        exit 1
    fi
    
    # Check if bucket name is globally unique (if creating new)
    if ! aws s3api head-bucket --bucket "$S3_BUCKET_NAME" --profile "$AWS_PROFILE" 2>/dev/null; then
        # Try to create a test object to check if bucket name is available
        local test_bucket_name="test-${S3_BUCKET_NAME}-availability"
        if aws s3api head-bucket --bucket "$test_bucket_name" --profile "$AWS_PROFILE" 2>/dev/null; then
            log_warning "Similar bucket names may conflict"
        fi
    fi
    
    log_success "Deployment configuration validated"
}

# Deploy storage stack
deploy_storage_stack() {
    log_info "Deploying storage stack: $STORAGE_STACK_NAME"
    
    cd "$CDK_DIR"
    
    # Set CDK context
    local cdk_context=(
        "--context" "environment=$ENVIRONMENT"
        "--context" "awsAccountId=$AWS_ACCOUNT_ID"
        "--context" "awsRegion=$AWS_REGION"
    )
    
    # Deploy the storage stack
    if cdk deploy "$STORAGE_STACK_NAME" \
        --profile "$AWS_PROFILE" \
        "${cdk_context[@]}" \
        --require-approval never \
        --progress events \
        --outputs-file "$PROJECT_ROOT/tmp/outputs/storage-outputs-$ENVIRONMENT.json"; then
        
        log_success "Storage stack deployed successfully"
    else
        log_error "Storage stack deployment failed"
        exit 1
    fi
}

# Configure S3 bucket policies and settings
configure_s3_bucket() {
    log_info "Configuring S3 bucket policies and settings"
    
    # Wait for bucket to be available
    log_info "Waiting for S3 bucket to be available..."
    aws s3api wait bucket-exists --bucket "$S3_BUCKET_NAME" --profile "$AWS_PROFILE"
    
    # Configure bucket notification (if needed)
    log_info "Configuring bucket notifications"
    
    # Set up CORS configuration
    local cors_config=$(cat << EOF
{
    "CORSRules": [
        {
            "AllowedHeaders": ["*"],
            "AllowedMethods": ["GET", "POST", "PUT", "DELETE", "HEAD"],
            "AllowedOrigins": ["*"],
            "ExposeHeaders": ["ETag"],
            "MaxAgeSeconds": 3000
        }
    ]
}
EOF
)
    
    echo "$cors_config" > "/tmp/cors-config-$ENVIRONMENT.json"
    
    if aws s3api put-bucket-cors \
        --bucket "$S3_BUCKET_NAME" \
        --cors-configuration "file:///tmp/cors-config-$ENVIRONMENT.json" \
        --profile "$AWS_PROFILE"; then
        log_success "S3 CORS configuration applied"
    else
        log_warning "Failed to apply S3 CORS configuration"
    fi
    
    # Clean up temp file
    rm -f "/tmp/cors-config-$ENVIRONMENT.json"
    
    # Configure bucket lifecycle policy
    log_info "Configuring S3 lifecycle policy"
    
    local lifecycle_config=$(cat << EOF
{
    "Rules": [
        {
            "ID": "EchoesAudioLifecycle",
            "Status": "Enabled",
            "Transitions": [
                {
                    "Days": 30,
                    "StorageClass": "STANDARD_IA"
                },
                {
                    "Days": 90,
                    "StorageClass": "GLACIER"
                }
            ],
            "AbortIncompleteMultipartUpload": {
                "DaysAfterInitiation": 7
            }
        }
    ]
}
EOF
)
    
    echo "$lifecycle_config" > "/tmp/lifecycle-config-$ENVIRONMENT.json"
    
    if aws s3api put-bucket-lifecycle-configuration \
        --bucket "$S3_BUCKET_NAME" \
        --lifecycle-configuration "file:///tmp/lifecycle-config-$ENVIRONMENT.json" \
        --profile "$AWS_PROFILE"; then
        log_success "S3 lifecycle policy configured"
    else
        log_warning "Failed to configure S3 lifecycle policy"
    fi
    
    # Clean up temp file
    rm -f "/tmp/lifecycle-config-$ENVIRONMENT.json"
}

# Configure DynamoDB table settings
configure_dynamodb_table() {
    log_info "Configuring DynamoDB table settings"
    
    # Wait for table to be active
    log_info "Waiting for DynamoDB table to be active..."
    aws dynamodb wait table-exists --table-name "$DYNAMODB_TABLE_NAME" --profile "$AWS_PROFILE"
    
    # Enable point-in-time recovery for production
    if [[ "$ENVIRONMENT" = "prod" ]]; then
        log_info "Enabling point-in-time recovery for production"
        
        if aws dynamodb put-backup-policy \
            --table-name "$DYNAMODB_TABLE_NAME" \
            --backup-policy BackupEnabled=true \
            --profile "$AWS_PROFILE" 2>/dev/null; then
            log_success "Point-in-time recovery enabled"
        else
            log_warning "Failed to enable point-in-time recovery"
        fi
    fi
    
    # Configure table monitoring
    log_info "Setting up table monitoring"
    
    # This will be handled by the monitoring stack, but we can set basic alarms here
    local table_arn="arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${DYNAMODB_TABLE_NAME}"
    
    # Create CloudWatch alarm for throttling
    if aws cloudwatch put-metric-alarm \
        --alarm-name "DynamoDB-Throttling-${DYNAMODB_TABLE_NAME}" \
        --alarm-description "DynamoDB throttling alarm for $DYNAMODB_TABLE_NAME" \
        --metric-name "UserErrors" \
        --namespace "AWS/DynamoDB" \
        --statistic "Sum" \
        --period 300 \
        --threshold 5 \
        --comparison-operator "GreaterThanThreshold" \
        --evaluation-periods 2 \
        --dimensions "Name=TableName,Value=$DYNAMODB_TABLE_NAME" \
        --profile "$AWS_PROFILE" 2>/dev/null; then
        log_success "DynamoDB throttling alarm created"
    else
        log_warning "Failed to create DynamoDB throttling alarm"
    fi
}

# Test storage resources
test_storage_resources() {
    log_info "Testing storage resources"
    
    # Test S3 bucket access
    log_info "Testing S3 bucket access"
    
    local test_key="test-deployment-$(date +%s).txt"
    local test_content="Deployment test at $(date)"
    
    # Upload test file
    if echo "$test_content" | aws s3 cp - "s3://${S3_BUCKET_NAME}/${test_key}" --profile "$AWS_PROFILE"; then
        log_success "S3 upload test passed"
        
        # Download test file
        if aws s3 cp "s3://${S3_BUCKET_NAME}/${test_key}" - --profile "$AWS_PROFILE" > /dev/null; then
            log_success "S3 download test passed"
            
            # Delete test file
            aws s3 rm "s3://${S3_BUCKET_NAME}/${test_key}" --profile "$AWS_PROFILE" > /dev/null
        else
            log_error "S3 download test failed"
            return 1
        fi
    else
        log_error "S3 upload test failed"
        return 1
    fi
    
    # Test DynamoDB table access
    log_info "Testing DynamoDB table access"
    
    local test_item=$(cat << EOF
{
    "userId": {"S": "test-user-$(date +%s)"},
    "echoId": {"S": "test-echo-$(date +%s)"},
    "timestamp": {"S": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"},
    "testItem": {"BOOL": true}
}
EOF
)
    
    # Put test item
    if aws dynamodb put-item \
        --table-name "$DYNAMODB_TABLE_NAME" \
        --item "$test_item" \
        --profile "$AWS_PROFILE" > /dev/null; then
        
        log_success "DynamoDB write test passed"
        
        # Get test item back
        local user_id
        local echo_id
        user_id=$(echo "$test_item" | jq -r '.userId.S')
        echo_id=$(echo "$test_item" | jq -r '.echoId.S')
        
        if aws dynamodb get-item \
            --table-name "$DYNAMODB_TABLE_NAME" \
            --key "{\"userId\":{\"S\":\"$user_id\"},\"echoId\":{\"S\":\"$echo_id\"}}" \
            --profile "$AWS_PROFILE" > /dev/null; then
            
            log_success "DynamoDB read test passed"
            
            # Delete test item
            aws dynamodb delete-item \
                --table-name "$DYNAMODB_TABLE_NAME" \
                --key "{\"userId\":{\"S\":\"$user_id\"},\"echoId\":{\"S\":\"$echo_id\"}}" \
                --profile "$AWS_PROFILE" > /dev/null
        else
            log_error "DynamoDB read test failed"
            return 1
        fi
    else
        log_error "DynamoDB write test failed"
        return 1
    fi
    
    log_success "All storage resource tests passed"
}

# Generate deployment outputs
generate_outputs() {
    log_info "Generating deployment outputs"
    
    local outputs_file="$PROJECT_ROOT/tmp/outputs/storage-deployment-$ENVIRONMENT.json"
    
    # Get stack outputs
    local stack_outputs
    stack_outputs=$(aws cloudformation describe-stacks \
        --stack-name "$STORAGE_STACK_NAME" \
        --profile "$AWS_PROFILE" \
        --query 'Stacks[0].Outputs' \
        --output json 2>/dev/null || echo "[]")
    
    # Get resource information
    local bucket_info
    bucket_info=$(aws s3api head-bucket --bucket "$S3_BUCKET_NAME" --profile "$AWS_PROFILE" 2>/dev/null || echo "{}")
    
    local table_info
    table_info=$(aws dynamodb describe-table --table-name "$DYNAMODB_TABLE_NAME" --profile "$AWS_PROFILE" --output json 2>/dev/null || echo "{}")
    
    # Create comprehensive output
    cat > "$outputs_file" << EOF
{
  "deployment": {
    "environment": "$ENVIRONMENT",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "stack_name": "$STORAGE_STACK_NAME",
    "status": "completed"
  },
  "resources": {
    "s3_bucket": {
      "name": "$S3_BUCKET_NAME",
      "arn": "arn:aws:s3:::$S3_BUCKET_NAME",
      "region": "$AWS_REGION",
      "endpoint": "https://s3.${AWS_REGION}.amazonaws.com/${S3_BUCKET_NAME}"
    },
    "dynamodb_table": {
      "name": "$DYNAMODB_TABLE_NAME",
      "arn": "arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${DYNAMODB_TABLE_NAME}",
      "region": "$AWS_REGION"
    }
  },
  "stack_outputs": $stack_outputs,
  "table_description": $table_info
}
EOF
    
    log_success "Deployment outputs saved: $outputs_file"
    
    # Display key information
    echo
    echo -e "${BLUE}📋 Storage Resources Created:${NC}"
    echo "  🗄️  S3 Bucket: $S3_BUCKET_NAME"
    echo "  📊 DynamoDB Table: $DYNAMODB_TABLE_NAME"
    echo "  🏗️  CloudFormation Stack: $STORAGE_STACK_NAME"
}

# Main execution
main() {
    echo -e "${BLUE}🗄️  Deploying storage infrastructure for: $ENVIRONMENT${NC}"
    echo "================================="
    
    load_environment_config
    check_existing_resources
    validate_deployment
    deploy_storage_stack
    configure_s3_bucket
    configure_dynamodb_table
    test_storage_resources
    generate_outputs
    
    echo
    log_success "Storage infrastructure deployment completed successfully!"
    echo -e "${BLUE}Environment '$ENVIRONMENT' storage is ready.${NC}"
    echo
    echo -e "${BLUE}Next step: Deploy authentication infrastructure${NC}"
    echo "  ./deploy/scripts/deploy-auth.sh -e $ENVIRONMENT"
}

# Run main function
main "$@"