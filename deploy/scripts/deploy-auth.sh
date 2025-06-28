#!/bin/bash

# Authentication Infrastructure Deployment Script for Echoes Backend
# Deploys Cognito User Pool, Identity Pool, and authentication services

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
Authentication Infrastructure Deployment Script

Usage: $0 [options]

Options:
  -e, --environment <env>  Environment to deploy (dev, staging, prod)
  -p, --profile <profile>  AWS profile to use
  -y, --yes               Skip confirmation prompts
  -f, --force             Force update existing resources
  -h, --help              Show this help message

This script deploys:
  1. Cognito User Pool with custom configuration
  2. Cognito User Pool Client
  3. Cognito Identity Pool
  4. IAM roles for authenticated/unauthenticated users
  5. Custom authentication flows and triggers
  6. Password policies and security settings
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

# Check storage dependencies
check_dependencies() {
    log_info "Checking deployment dependencies"
    
    # Check if storage stack exists
    if ! aws cloudformation describe-stacks --stack-name "$STORAGE_STACK_NAME" --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        log_error "Storage stack not found: $STORAGE_STACK_NAME"
        log_error "Run deploy-storage.sh first"
        exit 1
    fi
    
    # Check if S3 bucket exists
    if ! aws s3api head-bucket --bucket "$S3_BUCKET_NAME" --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        log_error "S3 bucket not found: $S3_BUCKET_NAME"
        log_error "Run deploy-storage.sh first"
        exit 1
    fi
    
    log_success "All dependencies are available"
}

# Check existing authentication resources
check_existing_resources() {
    log_info "Checking existing authentication resources"
    
    local auth_stack_exists=false
    
    # Check CloudFormation stack
    if aws cloudformation describe-stacks --stack-name "$AUTH_STACK_NAME" --profile "$AWS_PROFILE" 2>/dev/null; then
        auth_stack_exists=true
        log_warning "Authentication stack already exists: $AUTH_STACK_NAME"
    fi
    
    if [[ "$auth_stack_exists" = true ]] && [[ "$FORCE_UPDATE" = false ]]; then
        log_warning "Authentication resources already exist. Use --force to update them."
        if [[ "$SKIP_CONFIRMATION" = false ]]; then
            read -p "Continue with update? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                log_info "Deployment cancelled"
                exit 0
            fi
        fi
    fi
}

# Deploy authentication stack
deploy_auth_stack() {
    log_info "Deploying authentication stack: $AUTH_STACK_NAME"
    
    cd "$CDK_DIR"
    
    # Set CDK context
    local cdk_context=(
        "--context" "environment=$ENVIRONMENT"
        "--context" "awsAccountId=$AWS_ACCOUNT_ID"
        "--context" "awsRegion=$AWS_REGION"
    )
    
    # Deploy the authentication stack
    if cdk deploy "$AUTH_STACK_NAME" \
        --profile "$AWS_PROFILE" \
        "${cdk_context[@]}" \
        --require-approval never \
        --progress events \
        --outputs-file "$PROJECT_ROOT/tmp/outputs/auth-outputs-$ENVIRONMENT.json"; then
        
        log_success "Authentication stack deployed successfully"
    else
        log_error "Authentication stack deployment failed"
        exit 1
    fi
}

# Get authentication resource IDs
get_auth_resource_ids() {
    log_info "Retrieving authentication resource IDs"
    
    # Get stack outputs
    local stack_outputs
    stack_outputs=$(aws cloudformation describe-stacks \
        --stack-name "$AUTH_STACK_NAME" \
        --profile "$AWS_PROFILE" \
        --query 'Stacks[0].Outputs' \
        --output json 2>/dev/null || echo "[]")
    
    # Extract resource IDs from outputs
    USER_POOL_ID=$(echo "$stack_outputs" | jq -r '.[] | select(.OutputKey == "UserPoolId") | .OutputValue // empty')
    USER_POOL_CLIENT_ID=$(echo "$stack_outputs" | jq -r '.[] | select(.OutputKey == "UserPoolClientId") | .OutputValue // empty')
    IDENTITY_POOL_ID=$(echo "$stack_outputs" | jq -r '.[] | select(.OutputKey == "IdentityPoolId") | .OutputValue // empty')
    
    if [[ -z "$USER_POOL_ID" ]] || [[ -z "$USER_POOL_CLIENT_ID" ]]; then
        log_error "Failed to retrieve authentication resource IDs"
        exit 1
    fi
    
    log_success "Authentication resource IDs retrieved"
    log_info "User Pool ID: $USER_POOL_ID"
    log_info "User Pool Client ID: $USER_POOL_CLIENT_ID"
    if [[ -n "$IDENTITY_POOL_ID" ]]; then
        log_info "Identity Pool ID: $IDENTITY_POOL_ID"
    fi
    
    # Export for use in other scripts
    export USER_POOL_ID USER_POOL_CLIENT_ID IDENTITY_POOL_ID
}

# Configure User Pool additional settings
configure_user_pool_settings() {
    log_info "Configuring additional User Pool settings"
    
    # Configure user pool domain (if needed)
    local domain_name="echoes-${ENVIRONMENT}-${AWS_ACCOUNT_ID:0:8}"
    
    if aws cognito-idp describe-user-pool-domain --domain "$domain_name" --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        log_info "User Pool domain already exists: $domain_name"
    else
        log_info "Creating User Pool domain: $domain_name"
        
        if aws cognito-idp create-user-pool-domain \
            --domain "$domain_name" \
            --user-pool-id "$USER_POOL_ID" \
            --profile "$AWS_PROFILE" > /dev/null 2>&1; then
            log_success "User Pool domain created: $domain_name"
        else
            log_warning "Failed to create User Pool domain (may already exist)"
        fi
    fi
    
    # Configure email settings for production
    if [[ "$ENVIRONMENT" = "prod" ]]; then
        log_info "Configuring email settings for production"
        
        # Note: This would typically require SES verification
        log_warning "Manual setup required: Configure SES for email delivery in production"
        log_warning "Update User Pool email configuration to use SES"
    fi
}

# Create test user for development
create_test_user() {
    if [[ "$ENVIRONMENT" = "prod" ]]; then
        log_info "Skipping test user creation in production"
        return 0
    fi
    
    log_info "Creating test user for development"
    
    local test_username="testuser"
    local test_email="testuser@example.com"
    local test_password="TestPassword123!"
    
    # Check if test user already exists
    if aws cognito-idp admin-get-user \
        --user-pool-id "$USER_POOL_ID" \
        --username "$test_username" \
        --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        log_info "Test user already exists: $test_username"
        return 0
    fi
    
    # Create test user
    if aws cognito-idp admin-create-user \
        --user-pool-id "$USER_POOL_ID" \
        --username "$test_username" \
        --user-attributes Name=email,Value="$test_email" Name=email_verified,Value=true \
        --temporary-password "$test_password" \
        --message-action SUPPRESS \
        --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        
        log_success "Test user created: $test_username"
        
        # Set permanent password
        if aws cognito-idp admin-set-user-password \
            --user-pool-id "$USER_POOL_ID" \
            --username "$test_username" \
            --password "$test_password" \
            --permanent \
            --profile "$AWS_PROFILE" > /dev/null 2>&1; then
            log_success "Test user password set"
        else
            log_warning "Failed to set permanent password for test user"
        fi
    else
        log_warning "Failed to create test user"
    fi
    
    log_info "Test user credentials:"
    log_info "  Username: $test_username"
    log_info "  Email: $test_email"
    log_info "  Password: $test_password"
}

# Test authentication functionality
test_authentication() {
    log_info "Testing authentication functionality"
    
    # Test user pool configuration
    local user_pool_info
    user_pool_info=$(aws cognito-idp describe-user-pool \
        --user-pool-id "$USER_POOL_ID" \
        --profile "$AWS_PROFILE" \
        --output json 2>/dev/null || echo "{}")
    
    if [[ "$(echo "$user_pool_info" | jq -r '.UserPool.Id // empty')" = "$USER_POOL_ID" ]]; then
        log_success "User Pool configuration test passed"
    else
        log_error "User Pool configuration test failed"
        return 1
    fi
    
    # Test user pool client configuration
    local client_info
    client_info=$(aws cognito-idp describe-user-pool-client \
        --user-pool-id "$USER_POOL_ID" \
        --client-id "$USER_POOL_CLIENT_ID" \
        --profile "$AWS_PROFILE" \
        --output json 2>/dev/null || echo "{}")
    
    if [[ "$(echo "$client_info" | jq -r '.UserPoolClient.ClientId // empty')" = "$USER_POOL_CLIENT_ID" ]]; then
        log_success "User Pool Client configuration test passed"
    else
        log_error "User Pool Client configuration test failed"
        return 1
    fi
    
    # Test identity pool if exists
    if [[ -n "$IDENTITY_POOL_ID" ]]; then
        local identity_pool_info
        identity_pool_info=$(aws cognito-identity describe-identity-pool \
            --identity-pool-id "$IDENTITY_POOL_ID" \
            --profile "$AWS_PROFILE" \
            --output json 2>/dev/null || echo "{}")
        
        if [[ "$(echo "$identity_pool_info" | jq -r '.IdentityPoolId // empty')" = "$IDENTITY_POOL_ID" ]]; then
            log_success "Identity Pool configuration test passed"
        else
            log_warning "Identity Pool configuration test failed"
        fi
    fi
    
    # Test authentication flow (if test user exists)
    if [[ "$ENVIRONMENT" != "prod" ]]; then
        log_info "Testing authentication flow with test user"
        
        local test_username="testuser"
        local test_password="TestPassword123!"
        
        # Attempt authentication
        local auth_result
        auth_result=$(aws cognito-idp admin-initiate-auth \
            --user-pool-id "$USER_POOL_ID" \
            --client-id "$USER_POOL_CLIENT_ID" \
            --auth-flow ADMIN_NO_SRP_AUTH \
            --auth-parameters USERNAME="$test_username",PASSWORD="$test_password" \
            --profile "$AWS_PROFILE" \
            --output json 2>/dev/null || echo "{}")
        
        if [[ "$(echo "$auth_result" | jq -r '.AuthenticationResult.AccessToken // empty')" != "" ]]; then
            log_success "Authentication flow test passed"
        else
            log_warning "Authentication flow test failed (may be normal if test user doesn't exist)"
        fi
    fi
    
    log_success "Authentication functionality tests completed"
}

# Setup authentication monitoring
setup_auth_monitoring() {
    log_info "Setting up authentication monitoring"
    
    # Create CloudWatch alarms for authentication metrics
    local alarms=(
        "SignInSuccesses"
        "SignInFailures" 
        "SignUpSuccesses"
        "SignUpFailures"
    )
    
    for alarm in "${alarms[@]}"; do
        local alarm_name="Cognito-${alarm}-${USER_POOL_ID}"
        
        # Configure alarm thresholds based on environment
        local threshold
        case $alarm in
            *Failures)
                threshold=10
                ;;
            *)
                threshold=100
                ;;
        esac
        
        if aws cloudwatch put-metric-alarm \
            --alarm-name "$alarm_name" \
            --alarm-description "Cognito ${alarm} alarm for User Pool ${USER_POOL_ID}" \
            --metric-name "$alarm" \
            --namespace "AWS/Cognito" \
            --statistic "Sum" \
            --period 300 \
            --threshold "$threshold" \
            --comparison-operator "GreaterThanThreshold" \
            --evaluation-periods 2 \
            --dimensions "Name=UserPool,Value=$USER_POOL_ID" \
            --profile "$AWS_PROFILE" 2>/dev/null; then
            log_success "CloudWatch alarm created: $alarm_name"
        else
            log_warning "Failed to create CloudWatch alarm: $alarm_name"
        fi
    done
}

# Update environment configuration with auth details
update_environment_config() {
    log_info "Updating environment configuration with authentication details"
    
    local env_file="$PROJECT_ROOT/environments/$ENVIRONMENT/.env.infrastructure"
    local config_file="$PROJECT_ROOT/deploy/configs/$ENVIRONMENT/deployment.json"
    
    # Update environment file
    if [[ -f "$env_file" ]]; then
        # Add authentication configuration
        cat >> "$env_file" << EOF

# Authentication Configuration (Auto-generated)
COGNITO_USER_POOL_ID=$USER_POOL_ID
COGNITO_USER_POOL_CLIENT_ID=$USER_POOL_CLIENT_ID
COGNITO_IDENTITY_POOL_ID=$IDENTITY_POOL_ID
COGNITO_REGION=$AWS_REGION
COGNITO_USER_POOL_DOMAIN=echoes-${ENVIRONMENT}-${AWS_ACCOUNT_ID:0:8}
EOF
        
        log_success "Environment file updated with authentication details"
    fi
    
    # Update deployment configuration
    if [[ -f "$config_file" ]] && command -v jq &> /dev/null; then
        local temp_config="$config_file.tmp"
        
        jq --arg user_pool_id "$USER_POOL_ID" \
           --arg client_id "$USER_POOL_CLIENT_ID" \
           --arg identity_pool_id "$IDENTITY_POOL_ID" \
           '.resources.cognito.userPoolId = $user_pool_id |
            .resources.cognito.userPoolClientId = $client_id |
            .resources.cognito.identityPoolId = $identity_pool_id' \
           "$config_file" > "$temp_config" && mv "$temp_config" "$config_file"
        
        log_success "Deployment configuration updated"
    fi
}

# Generate authentication summary
generate_summary() {
    log_info "Generating authentication deployment summary"
    
    local summary_file="$PROJECT_ROOT/tmp/auth-deployment-$ENVIRONMENT.json"
    
    # Get detailed resource information
    local user_pool_info
    user_pool_info=$(aws cognito-idp describe-user-pool \
        --user-pool-id "$USER_POOL_ID" \
        --profile "$AWS_PROFILE" \
        --output json 2>/dev/null || echo "{}")
    
    local client_info
    client_info=$(aws cognito-idp describe-user-pool-client \
        --user-pool-id "$USER_POOL_ID" \
        --client-id "$USER_POOL_CLIENT_ID" \
        --profile "$AWS_PROFILE" \
        --output json 2>/dev/null || echo "{}")
    
    # Create comprehensive summary
    cat > "$summary_file" << EOF
{
  "deployment": {
    "environment": "$ENVIRONMENT",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "stack_name": "$AUTH_STACK_NAME",
    "status": "completed"
  },
  "resources": {
    "user_pool": {
      "id": "$USER_POOL_ID",
      "name": "$(echo "$user_pool_info" | jq -r '.UserPool.Name // ""')",
      "arn": "$(echo "$user_pool_info" | jq -r '.UserPool.Arn // ""')",
      "domain": "echoes-${ENVIRONMENT}-${AWS_ACCOUNT_ID:0:8}",
      "creation_date": "$(echo "$user_pool_info" | jq -r '.UserPool.CreationDate // ""')"
    },
    "user_pool_client": {
      "id": "$USER_POOL_CLIENT_ID",
      "name": "$(echo "$client_info" | jq -r '.UserPoolClient.ClientName // ""')"
    },
    "identity_pool": {
      "id": "$IDENTITY_POOL_ID"
    }
  },
  "configuration": {
    "password_policy": $(echo "$user_pool_info" | jq '.UserPool.Policies.PasswordPolicy // {}'),
    "mfa_configuration": "$(echo "$user_pool_info" | jq -r '.UserPool.MfaConfiguration // "OFF"')",
    "email_verification": "$(echo "$user_pool_info" | jq -r '.UserPool.AutoVerifiedAttributes // []' | jq 'contains(["email"])')"
  },
  "test_user_created": $([ "$ENVIRONMENT" != "prod" ] && echo "true" || echo "false"),
  "monitoring_configured": true
}
EOF
    
    log_success "Authentication summary saved: $summary_file"
    
    # Display key information
    echo
    echo -e "${BLUE}👤 Authentication Resources Created:${NC}"
    echo "  🔐 User Pool: $USER_POOL_ID"
    echo "  📱 User Pool Client: $USER_POOL_CLIENT_ID"
    if [[ -n "$IDENTITY_POOL_ID" ]]; then
        echo "  🆔 Identity Pool: $IDENTITY_POOL_ID"
    fi
    echo "  🌐 Domain: echoes-${ENVIRONMENT}-${AWS_ACCOUNT_ID:0:8}"
    echo "  🏗️  CloudFormation Stack: $AUTH_STACK_NAME"
    
    if [[ "$ENVIRONMENT" != "prod" ]]; then
        echo
        echo -e "${BLUE}🧪 Test User Credentials:${NC}"
        echo "  Username: testuser"
        echo "  Email: testuser@example.com"
        echo "  Password: TestPassword123!"
    fi
}

# Main execution
main() {
    echo -e "${BLUE}👤 Deploying authentication infrastructure for: $ENVIRONMENT${NC}"
    echo "================================="
    
    load_environment_config
    check_dependencies
    check_existing_resources
    deploy_auth_stack
    get_auth_resource_ids
    configure_user_pool_settings
    create_test_user
    test_authentication
    setup_auth_monitoring
    update_environment_config
    generate_summary
    
    echo
    log_success "Authentication infrastructure deployment completed successfully!"
    echo -e "${BLUE}Environment '$ENVIRONMENT' authentication is ready.${NC}"
    echo
    echo -e "${BLUE}Next step: Deploy API infrastructure${NC}"
    echo "  ./deploy/scripts/deploy-api.sh -e $ENVIRONMENT"
}

# Run main function
main "$@"