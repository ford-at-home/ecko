#!/bin/bash

# Infrastructure Preparation Script for Echoes Backend
# Prepares CDK infrastructure, synthesizes templates, and validates deployment readiness

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
SKIP_BOOTSTRAP=false
SKIP_SYNTH=false

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
        --skip-bootstrap)
            SKIP_BOOTSTRAP=true
            shift
            ;;
        --skip-synth)
            SKIP_SYNTH=true
            shift
            ;;
        -h|--help)
            cat << EOF
Infrastructure Preparation Script

Usage: $0 [options]

Options:
  -e, --environment <env>  Environment to prepare (dev, staging, prod)
  -p, --profile <profile>  AWS profile to use
  --skip-bootstrap        Skip CDK bootstrap (use if already bootstrapped)
  --skip-synth           Skip CloudFormation template synthesis
  -h, --help             Show this help message

This script:
  1. Bootstraps CDK in the target account/region
  2. Synthesizes CloudFormation templates
  3. Validates template syntax and parameters
  4. Prepares deployment artifacts
  5. Checks deployment prerequisites
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

# Validate CDK installation and version
validate_cdk() {
    log_info "Validating CDK installation"
    
    if ! command -v cdk &> /dev/null; then
        log_error "CDK CLI not found. Install with: npm install -g aws-cdk"
        exit 1
    fi
    
    local cdk_version
    cdk_version=$(cdk --version | cut -d' ' -f1)
    log_info "CDK version: $cdk_version"
    
    # Check minimum version (2.100.0)
    if [[ "$(echo "$cdk_version" | cut -d. -f1)" -lt 2 ]] || 
       [[ "$(echo "$cdk_version" | cut -d. -f1)" -eq 2 && "$(echo "$cdk_version" | cut -d. -f2)" -lt 100 ]]; then
        log_warning "CDK version $cdk_version may be outdated. Recommended: 2.100.0+"
    fi
    
    log_success "CDK validation completed"
}

# Bootstrap CDK
bootstrap_cdk() {
    if [[ "$SKIP_BOOTSTRAP" = true ]]; then
        log_info "Skipping CDK bootstrap"
        return 0
    fi
    
    log_info "Bootstrapping CDK"
    
    local qualifier="${ENVIRONMENT}echoes"
    local bootstrap_bucket="cdk-${AWS_ACCOUNT_ID}-${AWS_REGION}-${ENVIRONMENT}"
    
    # Check if already bootstrapped
    if aws s3api head-bucket --bucket "$bootstrap_bucket" --profile "$AWS_PROFILE" 2>/dev/null; then
        log_info "CDK already bootstrapped for this environment"
        return 0
    fi
    
    log_info "Running CDK bootstrap with qualifier: $qualifier"
    
    cd "$CDK_DIR"
    
    cdk bootstrap \
        "aws://${AWS_ACCOUNT_ID}/${AWS_REGION}" \
        --profile "$AWS_PROFILE" \
        --qualifier "$qualifier" \
        --cloudformation-execution-policies "arn:aws:iam::aws:policy/AdministratorAccess" \
        --bootstrap-bucket-name "$bootstrap_bucket" \
        --toolkit-stack-name "CDKToolkit-$ENVIRONMENT" \
        --tags "Environment=$ENVIRONMENT,Project=Echoes,ManagedBy=CDK"
    
    log_success "CDK bootstrap completed"
}

# Build CDK application
build_cdk_app() {
    log_info "Building CDK application"
    
    cd "$CDK_DIR"
    
    # Install dependencies
    if [[ ! -d "node_modules" ]] || [[ "package-lock.json" -nt "node_modules" ]]; then
        log_info "Installing CDK dependencies"
        npm ci
    fi
    
    # Build TypeScript
    log_info "Compiling TypeScript"
    npm run build
    
    log_success "CDK application built successfully"
}

# Synthesize CloudFormation templates
synthesize_templates() {
    if [[ "$SKIP_SYNTH" = true ]]; then
        log_info "Skipping template synthesis"
        return 0
    fi
    
    log_info "Synthesizing CloudFormation templates"
    
    cd "$CDK_DIR"
    
    # Clean previous synthesis
    rm -rf cdk.out
    
    # Synthesize all stacks
    cdk synth \
        --profile "$AWS_PROFILE" \
        --context "environment=$ENVIRONMENT" \
        --context "awsAccountId=$AWS_ACCOUNT_ID" \
        --context "awsRegion=$AWS_REGION" \
        --output cdk.out \
        --verbose
    
    # Copy templates to deploy directory
    local template_dir="$PROJECT_ROOT/deploy/templates/$ENVIRONMENT"
    mkdir -p "$template_dir"
    
    # Copy generated templates
    if [[ -d "cdk.out" ]]; then
        cp cdk.out/*.template.json "$template_dir/" 2>/dev/null || true
        cp cdk.out/*.assets.json "$template_dir/" 2>/dev/null || true
    fi
    
    log_success "Templates synthesized and copied to $template_dir"
}

# Validate CloudFormation templates
validate_templates() {
    log_info "Validating CloudFormation templates"
    
    local template_dir="$PROJECT_ROOT/deploy/templates/$ENVIRONMENT"
    local validation_errors=0
    
    if [[ ! -d "$template_dir" ]]; then
        log_error "Template directory not found: $template_dir"
        exit 1
    fi
    
    # Validate each template
    for template in "$template_dir"/*.template.json; do
        if [[ -f "$template" ]]; then
            local template_name
            template_name=$(basename "$template")
            log_info "Validating template: $template_name"
            
            if aws cloudformation validate-template \
                --template-body "file://$template" \
                --profile "$AWS_PROFILE" > /dev/null 2>&1; then
                log_success "✓ $template_name is valid"
            else
                log_error "✗ $template_name validation failed"
                ((validation_errors++))
            fi
        fi
    done
    
    if [[ $validation_errors -gt 0 ]]; then
        log_error "$validation_errors template(s) failed validation"
        exit 1
    fi
    
    log_success "All templates validated successfully"
}

# Check deployment prerequisites
check_deployment_prerequisites() {
    log_info "Checking deployment prerequisites"
    
    local errors=0
    
    # Check AWS permissions
    log_info "Checking AWS permissions"
    
    # Test S3 permissions
    if ! aws s3api list-buckets --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        log_error "Missing S3 permissions"
        ((errors++))
    fi
    
    # Test CloudFormation permissions
    if ! aws cloudformation list-stacks --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        log_error "Missing CloudFormation permissions"
        ((errors++))
    fi
    
    # Test Lambda permissions
    if ! aws lambda list-functions --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        log_error "Missing Lambda permissions"
        ((errors++))
    fi
    
    # Test DynamoDB permissions
    if ! aws dynamodb list-tables --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        log_error "Missing DynamoDB permissions"
        ((errors++))
    fi
    
    # Test Cognito permissions
    if ! aws cognito-idp list-user-pools --max-results 1 --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        log_error "Missing Cognito permissions"
        ((errors++))
    fi
    
    # Check quotas and limits
    log_info "Checking service quotas"
    
    # Check Lambda function count
    local lambda_count
    lambda_count=$(aws lambda list-functions --profile "$AWS_PROFILE" --query 'length(Functions)' --output text 2>/dev/null || echo "0")
    if [[ $lambda_count -gt 900 ]]; then
        log_warning "High Lambda function count: $lambda_count (limit: 1000)"
    fi
    
    # Check CloudFormation stack count
    local stack_count
    stack_count=$(aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --profile "$AWS_PROFILE" --query 'length(StackSummaries)' --output text 2>/dev/null || echo "0")
    if [[ $stack_count -gt 180 ]]; then
        log_warning "High CloudFormation stack count: $stack_count (limit: 200)"
    fi
    
    if [[ $errors -gt 0 ]]; then
        log_error "$errors prerequisite check(s) failed"
        exit 1
    fi
    
    log_success "All deployment prerequisites met"
}

# Prepare backend artifacts
prepare_backend_artifacts() {
    log_info "Preparing backend artifacts"
    
    local backend_dir="$PROJECT_ROOT/backend"
    local artifacts_dir="$PROJECT_ROOT/deploy/artifacts/$ENVIRONMENT"
    
    mkdir -p "$artifacts_dir"
    
    # Create deployment package for Lambda
    local lambda_package="$artifacts_dir/lambda-deployment.zip"
    
    cd "$backend_dir"
    
    # Create temporary directory for Lambda package
    local temp_dir
    temp_dir=$(mktemp -d)
    
    # Copy application files
    cp -r app/* "$temp_dir/" 2>/dev/null || true
    cp simple_lambda.py "$temp_dir/" 2>/dev/null || true
    cp lambda_handler.py "$temp_dir/" 2>/dev/null || true
    cp requirements.txt "$temp_dir/" 2>/dev/null || true
    
    # Install dependencies if requirements.txt exists
    if [[ -f "$temp_dir/requirements.txt" ]]; then
        log_info "Installing Python dependencies for Lambda"
        pip install -r "$temp_dir/requirements.txt" -t "$temp_dir" --no-deps --quiet
    fi
    
    # Create zip package
    cd "$temp_dir"
    zip -r "$lambda_package" . -q
    
    # Cleanup
    rm -rf "$temp_dir"
    
    log_success "Backend artifacts prepared: $lambda_package"
}

# Generate deployment plan
generate_deployment_plan() {
    log_info "Generating deployment plan"
    
    local plan_file="$PROJECT_ROOT/deploy/configs/$ENVIRONMENT/deployment-plan.json"
    local stacks=("Storage" "Auth" "Api" "Notif")
    
    # Create deployment plan
    cat > "$plan_file" << EOF
{
  "deployment_plan": {
    "environment": "$ENVIRONMENT",
    "aws_account": "$AWS_ACCOUNT_ID",
    "aws_region": "$AWS_REGION",
    "generated": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  },
  "stacks": [
EOF
    
    local first=true
    for stack in "${stacks[@]}"; do
        if [[ "$first" = true ]]; then
            first=false
        else
            echo "," >> "$plan_file"
        fi
        
        cat >> "$plan_file" << EOF
    {
      "name": "Echoes-${stack}-${ENVIRONMENT}",
      "type": "$stack",
      "depends_on": $(case $stack in
        Storage) echo "[]" ;;
        Auth) echo "[\"Echoes-Storage-${ENVIRONMENT}\"]" ;;
        Api) echo "[\"Echoes-Storage-${ENVIRONMENT}\", \"Echoes-Auth-${ENVIRONMENT}\"]" ;;
        Notif) echo "[\"Echoes-Storage-${ENVIRONMENT}\", \"Echoes-Auth-${ENVIRONMENT}\"]" ;;
      esac),
      "template_file": "${stack}-${ENVIRONMENT}.template.json",
      "timeout": 30,
      "rollback_timeout": 15
    }EOF
    done
    
    cat >> "$plan_file" << EOF

  ],
  "deployment_order": [
    "Echoes-Storage-${ENVIRONMENT}",
    "Echoes-Auth-${ENVIRONMENT}",
    "Echoes-Api-${ENVIRONMENT}",
    "Echoes-Notif-${ENVIRONMENT}"
  ],
  "rollback_order": [
    "Echoes-Notif-${ENVIRONMENT}",
    "Echoes-Api-${ENVIRONMENT}",
    "Echoes-Auth-${ENVIRONMENT}",
    "Echoes-Storage-${ENVIRONMENT}"
  ]
}
EOF
    
    log_success "Deployment plan generated: $plan_file"
}

# Generate summary
generate_summary() {
    log_info "Generating preparation summary"
    
    local summary_file="$PROJECT_ROOT/tmp/infrastructure-prep-$ENVIRONMENT.json"
    
    cat > "$summary_file" << EOF
{
  "preparation": {
    "environment": "$ENVIRONMENT",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "aws_account": "$AWS_ACCOUNT_ID",
    "aws_region": "$AWS_REGION",
    "cdk_version": "$(cdk --version | cut -d' ' -f1)"
  },
  "artifacts": {
    "templates_dir": "deploy/templates/$ENVIRONMENT",
    "configs_dir": "deploy/configs/$ENVIRONMENT",
    "artifacts_dir": "deploy/artifacts/$ENVIRONMENT",
    "cdk_output": "cdk/cdk.out"
  },
  "stacks_prepared": [
    "Echoes-Storage-$ENVIRONMENT",
    "Echoes-Auth-$ENVIRONMENT",
    "Echoes-Api-$ENVIRONMENT",
    "Echoes-Notif-$ENVIRONMENT"
  ],
  "status": "ready"
}
EOF
    
    log_success "Preparation summary saved: $summary_file"
}

# Main execution
main() {
    echo -e "${BLUE}🏗️  Preparing infrastructure for: $ENVIRONMENT${NC}"
    echo "================================="
    
    load_environment_config
    validate_cdk
    build_cdk_app
    bootstrap_cdk
    synthesize_templates
    validate_templates
    check_deployment_prerequisites
    prepare_backend_artifacts
    generate_deployment_plan
    generate_summary
    
    echo
    log_success "Infrastructure preparation completed successfully!"
    echo -e "${BLUE}Environment '$ENVIRONMENT' is ready for deployment.${NC}"
    echo
    echo -e "${BLUE}Next steps:${NC}"
    echo "  1. Deploy storage: ./deploy/scripts/deploy-storage.sh -e $ENVIRONMENT"
    echo "  2. Deploy authentication: ./deploy/scripts/deploy-auth.sh -e $ENVIRONMENT"
    echo "  3. Deploy API: ./deploy/scripts/deploy-api.sh -e $ENVIRONMENT"
}

# Run main function
main "$@"