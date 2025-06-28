#!/bin/bash

# Enhanced S3 Setup Script for Echoes Audio Storage
# Configures S3 bucket with secure policies and CORS settings

set -e

# Configuration
ENVIRONMENT="${1:-dev}"
AWS_PROFILE="${2:-default}"
BUCKET_NAME="echoes-audio-${ENVIRONMENT}"
REGION="${AWS_REGION:-us-east-1}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check dependencies
check_dependencies() {
    log_info "Checking dependencies..."
    
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install AWS CLI."
        exit 1
    fi
    
    if ! command -v jq &> /dev/null; then
        log_error "jq not found. Please install jq for JSON processing."
        exit 1
    fi
    
    log_info "Dependencies check passed."
}

# Check AWS credentials
check_aws_credentials() {
    log_info "Checking AWS credentials for profile: ${AWS_PROFILE}"
    
    if ! aws sts get-caller-identity --profile "${AWS_PROFILE}" &> /dev/null; then
        log_error "AWS credentials not configured for profile: ${AWS_PROFILE}"
        log_error "Please run: aws configure --profile ${AWS_PROFILE}"
        exit 1
    fi
    
    local ACCOUNT_ID=$(aws sts get-caller-identity --profile "${AWS_PROFILE}" --query Account --output text)
    log_info "Using AWS Account: ${ACCOUNT_ID}"
}

# Create S3 bucket
create_bucket() {
    log_info "Creating S3 bucket: ${BUCKET_NAME}"
    
    # Check if bucket already exists
    if aws s3 ls "s3://${BUCKET_NAME}" --profile "${AWS_PROFILE}" &> /dev/null; then
        log_warn "Bucket ${BUCKET_NAME} already exists."
        return 0
    fi
    
    # Create bucket
    if [ "${REGION}" = "us-east-1" ]; then
        aws s3 mb "s3://${BUCKET_NAME}" --profile "${AWS_PROFILE}"
    else
        aws s3 mb "s3://${BUCKET_NAME}" --region "${REGION}" --profile "${AWS_PROFILE}"
    fi
    
    log_info "Bucket created successfully."
}

# Configure bucket encryption
configure_encryption() {
    log_info "Configuring bucket encryption..."
    
    aws s3api put-bucket-encryption \
        --bucket "${BUCKET_NAME}" \
        --profile "${AWS_PROFILE}" \
        --server-side-encryption-configuration '{
            "Rules": [
                {
                    "ApplyServerSideEncryptionByDefault": {
                        "SSEAlgorithm": "AES256"
                    },
                    "BucketKeyEnabled": true
                }
            ]
        }'
    
    log_info "Bucket encryption configured."
}

# Configure bucket versioning
configure_versioning() {
    log_info "Configuring bucket versioning..."
    
    aws s3api put-bucket-versioning \
        --bucket "${BUCKET_NAME}" \
        --profile "${AWS_PROFILE}" \
        --versioning-configuration Status=Suspended
    
    log_info "Bucket versioning configured."
}

# Configure public access block
configure_public_access_block() {
    log_info "Configuring public access block..."
    
    aws s3api put-public-access-block \
        --bucket "${BUCKET_NAME}" \
        --profile "${AWS_PROFILE}" \
        --public-access-block-configuration \
            BlockPublicAcls=true,\
            IgnorePublicAcls=true,\
            BlockPublicPolicy=false,\
            RestrictPublicBuckets=false
    
    log_info "Public access block configured."
}

# Configure CORS
configure_cors() {
    log_info "Configuring CORS..."
    
    local CORS_FILE="backend/config/s3-cors-enhanced.json"
    
    if [ ! -f "${CORS_FILE}" ]; then
        log_error "CORS configuration file not found: ${CORS_FILE}"
        return 1
    fi
    
    aws s3api put-bucket-cors \
        --bucket "${BUCKET_NAME}" \
        --profile "${AWS_PROFILE}" \
        --cors-configuration "file://${CORS_FILE}"
    
    log_info "CORS configured successfully."
}

# Configure bucket policy
configure_bucket_policy() {
    log_info "Configuring bucket policy..."
    
    local POLICY_TEMPLATE="backend/config/s3-bucket-policy-enhanced.json"
    local POLICY_FILE="/tmp/s3-bucket-policy-${BUCKET_NAME}.json"
    
    if [ ! -f "${POLICY_TEMPLATE}" ]; then
        log_error "Bucket policy template not found: ${POLICY_TEMPLATE}"
        return 1
    fi
    
    # Replace placeholders in policy template
    sed "s/\${BUCKET_NAME}/${BUCKET_NAME}/g" "${POLICY_TEMPLATE}" > "${POLICY_FILE}"
    
    aws s3api put-bucket-policy \
        --bucket "${BUCKET_NAME}" \
        --profile "${AWS_PROFILE}" \
        --policy "file://${POLICY_FILE}"
    
    # Clean up temporary file
    rm -f "${POLICY_FILE}"
    
    log_info "Bucket policy configured successfully."
}

# Configure lifecycle rules
configure_lifecycle() {
    log_info "Configuring lifecycle rules..."
    
    local LIFECYCLE_CONFIG='{
        "Rules": [
            {
                "ID": "DeleteOldVersions",
                "Status": "Enabled",
                "Filter": {},
                "Expiration": {
                    "Days": 365
                },
                "AbortIncompleteMultipartUpload": {
                    "DaysAfterInitiation": 7
                }
            },
            {
                "ID": "TransitionToIA",
                "Status": "Enabled",
                "Filter": {},
                "Transitions": [
                    {
                        "Days": 30,
                        "StorageClass": "STANDARD_IA"
                    },
                    {
                        "Days": 90,
                        "StorageClass": "GLACIER"
                    }
                ]
            }
        ]
    }'
    
    echo "${LIFECYCLE_CONFIG}" > "/tmp/lifecycle-${BUCKET_NAME}.json"
    
    aws s3api put-bucket-lifecycle-configuration \
        --bucket "${BUCKET_NAME}" \
        --profile "${AWS_PROFILE}" \
        --lifecycle-configuration "file:///tmp/lifecycle-${BUCKET_NAME}.json"
    
    # Clean up temporary file
    rm -f "/tmp/lifecycle-${BUCKET_NAME}.json"
    
    log_info "Lifecycle rules configured successfully."
}

# Enable CloudTrail logging (optional)
configure_logging() {
    log_info "Configuring access logging..."
    
    local LOG_BUCKET="${BUCKET_NAME}-logs"
    
    # Create logs bucket if it doesn't exist
    if ! aws s3 ls "s3://${LOG_BUCKET}" --profile "${AWS_PROFILE}" &> /dev/null; then
        log_info "Creating logs bucket: ${LOG_BUCKET}"
        
        if [ "${REGION}" = "us-east-1" ]; then
            aws s3 mb "s3://${LOG_BUCKET}" --profile "${AWS_PROFILE}"
        else
            aws s3 mb "s3://${LOG_BUCKET}" --region "${REGION}" --profile "${AWS_PROFILE}"
        fi
    fi
    
    # Configure access logging
    aws s3api put-bucket-logging \
        --bucket "${BUCKET_NAME}" \
        --profile "${AWS_PROFILE}" \
        --bucket-logging-status '{
            "LoggingEnabled": {
                "TargetBucket": "'${LOG_BUCKET}'",
                "TargetPrefix": "access-logs/"
            }
        }'
    
    log_info "Access logging configured."
}

# Verify configuration
verify_configuration() {
    log_info "Verifying S3 configuration..."
    
    # Check encryption
    local ENCRYPTION=$(aws s3api get-bucket-encryption --bucket "${BUCKET_NAME}" --profile "${AWS_PROFILE}" 2>/dev/null || echo "")
    if [ -n "${ENCRYPTION}" ]; then
        log_info "✓ Encryption: Enabled"
    else
        log_warn "✗ Encryption: Not configured"
    fi
    
    # Check CORS
    local CORS=$(aws s3api get-bucket-cors --bucket "${BUCKET_NAME}" --profile "${AWS_PROFILE}" 2>/dev/null || echo "")
    if [ -n "${CORS}" ]; then
        log_info "✓ CORS: Configured"
    else
        log_warn "✗ CORS: Not configured"
    fi
    
    # Check policy
    local POLICY=$(aws s3api get-bucket-policy --bucket "${BUCKET_NAME}" --profile "${AWS_PROFILE}" 2>/dev/null || echo "")
    if [ -n "${POLICY}" ]; then
        log_info "✓ Bucket Policy: Configured"
    else
        log_warn "✗ Bucket Policy: Not configured"
    fi
    
    log_info "Configuration verification completed."
}

# Generate environment configuration
generate_env_config() {
    log_info "Generating environment configuration..."
    
    local ENV_FILE=".env.${ENVIRONMENT}"
    
    cat > "${ENV_FILE}" << EOF
# S3 Configuration for ${ENVIRONMENT}
S3_BUCKET_NAME=${BUCKET_NAME}
AWS_REGION=${REGION}
AWS_PROFILE=${AWS_PROFILE}

# Generated on $(date)
EOF
    
    log_info "Environment configuration saved to: ${ENV_FILE}"
}

# Main execution
main() {
    log_info "Starting enhanced S3 setup for environment: ${ENVIRONMENT}"
    log_info "Using AWS profile: ${AWS_PROFILE}"
    log_info "Target bucket: ${BUCKET_NAME}"
    log_info "Region: ${REGION}"
    
    check_dependencies
    check_aws_credentials
    create_bucket
    configure_encryption
    configure_versioning
    configure_public_access_block
    configure_cors
    configure_bucket_policy
    configure_lifecycle
    
    # Optional: Enable logging (uncomment if needed)
    # configure_logging
    
    verify_configuration
    generate_env_config
    
    log_info "S3 setup completed successfully!"
    log_info "Bucket URL: https://${BUCKET_NAME}.s3.${REGION}.amazonaws.com"
    log_info "Next steps:"
    log_info "1. Update your application configuration with the bucket name"
    log_info "2. Test presigned URL generation"
    log_info "3. Verify CORS settings with your frontend"
}

# Show usage
show_usage() {
    echo "Usage: $0 [environment] [aws-profile]"
    echo ""
    echo "Arguments:"
    echo "  environment  Environment name (default: dev)"
    echo "  aws-profile  AWS profile name (default: default)"
    echo ""
    echo "Examples:"
    echo "  $0                          # Use dev environment with default profile"
    echo "  $0 prod                     # Use prod environment with default profile"
    echo "  $0 dev my-profile          # Use dev environment with my-profile"
    echo ""
}

# Handle help flag
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    show_usage
    exit 0
fi

# Run main function
main "$@"