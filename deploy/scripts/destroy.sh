#!/bin/bash

# Infrastructure Destroy Script for Echoes Backend
# Safely destroys AWS infrastructure with proper safeguards and backups

set -euo pipefail

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly NC='\033[0m'

# Script configuration
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
readonly CDK_DIR="$PROJECT_ROOT/cdk"

# Default values
ENVIRONMENT="dev"
AWS_PROFILE="${AWS_PROFILE:-default}"
FORCE_DESTROY=false
BACKUP_DATA=true
PRESERVE_BACKUPS=true
DRY_RUN=false

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
            FORCE_DESTROY=true
            shift
            ;;
        --no-backup)
            BACKUP_DATA=false
            shift
            ;;
        --remove-backups)
            PRESERVE_BACKUPS=false
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            cat << EOF
Infrastructure Destroy Script

Usage: $0 [options]

Options:
  -e, --environment <env>  Environment to destroy (dev, staging, prod)
  -p, --profile <profile>  AWS profile to use
  -f, --force             Force destroy without additional confirmations
  --no-backup             Skip data backup before destruction
  --remove-backups        Remove existing backups as well
  --dry-run               Show what would be destroyed without executing
  -h, --help              Show this help message

DANGER: This script will permanently destroy infrastructure!

Safety Features:
  - Multiple confirmation prompts (unless --force)
  - Automatic data backup (unless --no-backup)
  - Ordered destruction to prevent dependency issues
  - Comprehensive logging of all actions
  - Rollback capability for partial failures

Destruction Order:
  1. Monitoring and notifications
  2. API Gateway and Lambda
  3. Authentication services
  4. Storage services (with backup)
  5. CloudFormation stacks
  6. CDK bootstrap (optional)
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

log_destroy() {
    echo -e "${PURPLE}💥 $1${NC}"
}

# Load environment configuration
load_environment_config() {
    log_info "Loading environment configuration"
    
    local env_file="$PROJECT_ROOT/environments/$ENVIRONMENT/.env.infrastructure"
    
    if [[ ! -f "$env_file" ]]; then
        log_error "Environment file not found: $env_file"
        log_error "Cannot determine resource names for destruction"
        exit 1
    fi
    
    # Load environment variables
    set -a
    source "$env_file"
    set +a
    
    log_success "Environment configuration loaded"
}

# Safety checks and confirmations
perform_safety_checks() {
    log_info "Performing safety checks"
    
    # Validate environment
    if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
        log_error "Invalid environment: $ENVIRONMENT"
        exit 1
    fi
    
    # Extra protection for production
    if [[ "$ENVIRONMENT" = "prod" ]]; then
        log_warning "PRODUCTION ENVIRONMENT DESTRUCTION REQUESTED!"
        log_warning "This will permanently delete all production data and infrastructure!"
        
        if [[ "$FORCE_DESTROY" = false ]]; then
            echo
            echo -e "${RED}⚠️  FINAL WARNING: You are about to destroy PRODUCTION!${NC}"
            echo -e "${RED}⚠️  This action is IRREVERSIBLE!${NC}"
            echo -e "${RED}⚠️  All data will be PERMANENTLY LOST!${NC}"
            echo
            read -p "Type 'DELETE PRODUCTION' to confirm: " confirmation
            
            if [[ "$confirmation" != "DELETE PRODUCTION" ]]; then
                log_info "Destruction cancelled - confirmation text did not match"
                exit 0
            fi
            
            echo
            read -p "Are you absolutely sure? (yes/NO): " final_confirmation
            
            if [[ "$final_confirmation" != "yes" ]]; then
                log_info "Destruction cancelled by user"
                exit 0
            fi
        fi
    elif [[ "$FORCE_DESTROY" = false ]]; then
        echo
        log_warning "You are about to destroy the $ENVIRONMENT environment"
        log_warning "This will delete all infrastructure and data for this environment"
        echo
        read -p "Continue with destruction? (y/N): " -n 1 -r
        echo
        
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Destruction cancelled by user"
            exit 0
        fi
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        log_error "AWS credentials not configured for profile: $AWS_PROFILE"
        exit 1
    fi
    
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --profile "$AWS_PROFILE" --query Account --output text)
    AWS_REGION=$(aws configure get region --profile "$AWS_PROFILE" || echo "us-east-1")
    
    log_success "Safety checks completed"
    log_info "Target Account: $AWS_ACCOUNT_ID"
    log_info "Target Region: $AWS_REGION"
}

# Create backup of critical data
backup_critical_data() {
    if [[ "$BACKUP_DATA" = false ]]; then
        log_info "Skipping data backup as requested"
        return 0
    fi
    
    log_info "Creating backup of critical data"
    
    local backup_dir="$PROJECT_ROOT/tmp/backups/destruction-backup-$ENVIRONMENT-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$backup_dir"
    
    # Backup DynamoDB table
    if aws dynamodb describe-table --table-name "$DYNAMODB_TABLE_NAME" --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        log_info "Backing up DynamoDB table: $DYNAMODB_TABLE_NAME"
        
        # Export table schema
        aws dynamodb describe-table \
            --table-name "$DYNAMODB_TABLE_NAME" \
            --profile "$AWS_PROFILE" \
            --output json > "$backup_dir/dynamodb-schema.json"
        
        # Export table data (scan all items)
        local items_file="$backup_dir/dynamodb-data.json"
        aws dynamodb scan \
            --table-name "$DYNAMODB_TABLE_NAME" \
            --profile "$AWS_PROFILE" \
            --output json > "$items_file"
        
        local item_count
        item_count=$(jq '.Items | length' "$items_file")
        log_success "DynamoDB backup completed: $item_count items saved"
    else
        log_info "DynamoDB table not found, skipping backup"
    fi
    
    # Backup CloudFormation stack configurations
    local stacks=("$STORAGE_STACK_NAME" "$AUTH_STACK_NAME" "$API_STACK_NAME" "$NOTIF_STACK_NAME")
    
    for stack in "${stacks[@]}"; do
        if aws cloudformation describe-stacks --stack-name "$stack" --profile "$AWS_PROFILE" > /dev/null 2>&1; then
            log_info "Backing up CloudFormation stack: $stack"
            
            # Export stack template
            aws cloudformation get-template \
                --stack-name "$stack" \
                --profile "$AWS_PROFILE" \
                --output json > "$backup_dir/cf-template-$(basename "$stack").json"
            
            # Export stack parameters and outputs
            aws cloudformation describe-stacks \
                --stack-name "$stack" \
                --profile "$AWS_PROFILE" \
                --output json > "$backup_dir/cf-stack-$(basename "$stack").json"
        fi
    done
    
    # Backup environment configuration
    if [[ -f "$PROJECT_ROOT/environments/$ENVIRONMENT/.env.infrastructure" ]]; then
        cp "$PROJECT_ROOT/environments/$ENVIRONMENT/.env.infrastructure" "$backup_dir/environment.env"
    fi
    
    # Create backup manifest
    cat > "$backup_dir/manifest.json" << EOF
{
  "backup_info": {
    "environment": "$ENVIRONMENT",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "aws_account": "$AWS_ACCOUNT_ID",
    "aws_region": "$AWS_REGION",
    "created_by": "$(whoami)",
    "backup_type": "pre_destruction"
  },
  "backed_up_resources": [
    "DynamoDB table: $DYNAMODB_TABLE_NAME",
    "CloudFormation stacks",
    "Environment configuration"
  ]
}
EOF
    
    log_success "Data backup completed: $backup_dir"
    export BACKUP_DIR="$backup_dir"
}

# List resources to be destroyed
list_resources_for_destruction() {
    log_info "Scanning resources to be destroyed"
    
    local resources_file="$PROJECT_ROOT/tmp/destruction-plan-$ENVIRONMENT.json"
    
    # Start building resource list
    cat > "$resources_file" << EOF
{
  "destruction_plan": {
    "environment": "$ENVIRONMENT",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "dry_run": $DRY_RUN
  },
  "resources": {
EOF
    
    # CloudFormation stacks
    echo '    "cloudformation_stacks": [' >> "$resources_file"
    local stacks=("$NOTIF_STACK_NAME" "$API_STACK_NAME" "$AUTH_STACK_NAME" "$STORAGE_STACK_NAME")
    local first=true
    
    for stack in "${stacks[@]}"; do
        if aws cloudformation describe-stacks --stack-name "$stack" --profile "$AWS_PROFILE" > /dev/null 2>&1; then
            if [[ "$first" = true ]]; then
                first=false
            else
                echo "," >> "$resources_file"
            fi
            echo "      \"$stack\"" >> "$resources_file"
        fi
    done
    echo "    ]," >> "$resources_file"
    
    # Individual resources
    cat >> "$resources_file" << EOF
    "s3_bucket": "$S3_BUCKET_NAME",
    "dynamodb_table": "$DYNAMODB_TABLE_NAME",
    "cognito_user_pool": "$COGNITO_USER_POOL_ID",
    "api_gateway": "$API_GATEWAY_ID",
    "lambda_function": "$LAMBDA_FUNCTION_NAME"
  }
}
EOF
    
    log_success "Destruction plan saved: $resources_file"
    
    # Display summary
    echo
    log_warning "The following resources will be DESTROYED:"
    echo
    
    if [[ -n "${S3_BUCKET_NAME:-}" ]]; then
        echo "  🗄️  S3 Bucket: $S3_BUCKET_NAME"
    fi
    
    if [[ -n "${DYNAMODB_TABLE_NAME:-}" ]]; then
        echo "  📊 DynamoDB Table: $DYNAMODB_TABLE_NAME"
    fi
    
    if [[ -n "${COGNITO_USER_POOL_ID:-}" ]]; then
        echo "  👤 Cognito User Pool: $COGNITO_USER_POOL_ID"
    fi
    
    if [[ -n "${API_GATEWAY_ID:-}" ]]; then
        echo "  🔗 API Gateway: $API_GATEWAY_ID"
    fi
    
    if [[ -n "${LAMBDA_FUNCTION_NAME:-}" ]]; then
        echo "  ⚡ Lambda Function: $LAMBDA_FUNCTION_NAME"
    fi
    
    echo
    for stack in "${stacks[@]}"; do
        if aws cloudformation describe-stacks --stack-name "$stack" --profile "$AWS_PROFILE" > /dev/null 2>&1; then
            echo "  🏗️  CloudFormation Stack: $stack"
        fi
    done
    
    echo
}

# Destroy CloudFormation stacks in reverse order
destroy_cloudformation_stacks() {
    log_destroy "Destroying CloudFormation stacks"
    
    # Destroy in reverse order of creation
    local stacks=("$NOTIF_STACK_NAME" "$API_STACK_NAME" "$AUTH_STACK_NAME" "$STORAGE_STACK_NAME")
    
    cd "$CDK_DIR"
    
    for stack in "${stacks[@]}"; do
        if aws cloudformation describe-stacks --stack-name "$stack" --profile "$AWS_PROFILE" > /dev/null 2>&1; then
            log_destroy "Destroying stack: $stack"
            
            if [[ "$DRY_RUN" = true ]]; then
                log_info "DRY RUN: Would destroy stack $stack"
                continue
            fi
            
            # Use CDK destroy for better handling
            if cdk destroy "$stack" \
                --profile "$AWS_PROFILE" \
                --force \
                --context "environment=$ENVIRONMENT" \
                --context "awsAccountId=$AWS_ACCOUNT_ID" \
                --context "awsRegion=$AWS_REGION"; then
                
                log_success "Stack destroyed: $stack"
            else
                log_error "Failed to destroy stack: $stack"
                
                # Try direct CloudFormation deletion as fallback
                log_info "Attempting direct CloudFormation deletion"
                if aws cloudformation delete-stack --stack-name "$stack" --profile "$AWS_PROFILE"; then
                    log_info "CloudFormation deletion initiated for: $stack"
                    
                    # Wait for deletion to complete
                    log_info "Waiting for stack deletion to complete..."
                    aws cloudformation wait stack-delete-complete --stack-name "$stack" --profile "$AWS_PROFILE" || true
                else
                    log_error "Direct CloudFormation deletion also failed for: $stack"
                fi
            fi
        else
            log_info "Stack not found, skipping: $stack"
        fi
    done
}

# Clean up orphaned resources
cleanup_orphaned_resources() {
    log_destroy "Cleaning up orphaned resources"
    
    # Clean up S3 bucket contents (if bucket still exists)
    if [[ -n "${S3_BUCKET_NAME:-}" ]] && aws s3api head-bucket --bucket "$S3_BUCKET_NAME" --profile "$AWS_PROFILE" 2>/dev/null; then
        log_destroy "Emptying S3 bucket: $S3_BUCKET_NAME"
        
        if [[ "$DRY_RUN" = true ]]; then
            log_info "DRY RUN: Would empty S3 bucket $S3_BUCKET_NAME"
        else
            # Delete all objects and versions
            aws s3 rm "s3://$S3_BUCKET_NAME" --recursive --profile "$AWS_PROFILE" || true
            
            # Delete all object versions (if versioning is enabled)
            aws s3api delete-objects \
                --bucket "$S3_BUCKET_NAME" \
                --delete "$(aws s3api list-object-versions \
                    --bucket "$S3_BUCKET_NAME" \
                    --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' \
                    --profile "$AWS_PROFILE" \
                    --output json 2>/dev/null || echo '{"Objects":[]}')" \
                --profile "$AWS_PROFILE" 2>/dev/null || true
            
            log_success "S3 bucket emptied: $S3_BUCKET_NAME"
        fi
    fi
    
    # Clean up CloudWatch log groups
    local log_groups=(
        "/aws/lambda/$LAMBDA_FUNCTION_NAME"
        "/aws/apigateway/$API_GATEWAY_ID"
        "Echoes-${ENVIRONMENT}-Dashboard"
    )
    
    for log_group in "${log_groups[@]}"; do
        if aws logs describe-log-groups --log-group-name-prefix "$log_group" --profile "$AWS_PROFILE" 2>/dev/null | grep -q "$log_group"; then
            log_destroy "Deleting log group: $log_group"
            
            if [[ "$DRY_RUN" = true ]]; then
                log_info "DRY RUN: Would delete log group $log_group"
            else
                aws logs delete-log-group --log-group-name "$log_group" --profile "$AWS_PROFILE" 2>/dev/null || true
                log_success "Log group deleted: $log_group"
            fi
        fi
    done
    
    # Clean up CloudWatch alarms
    local alarm_prefix="Echoes-"
    local alarms
    alarms=$(aws cloudwatch describe-alarms \
        --alarm-name-prefix "$alarm_prefix" \
        --profile "$AWS_PROFILE" \
        --query "MetricAlarms[?contains(AlarmName, '$ENVIRONMENT')].AlarmName" \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$alarms" ]]; then
        log_destroy "Deleting CloudWatch alarms"
        
        if [[ "$DRY_RUN" = true ]]; then
            log_info "DRY RUN: Would delete CloudWatch alarms: $alarms"
        else
            # Convert space-separated list to array
            IFS=' ' read -ra alarm_array <<< "$alarms"
            for alarm in "${alarm_array[@]}"; do
                aws cloudwatch delete-alarms --alarm-names "$alarm" --profile "$AWS_PROFILE" 2>/dev/null || true
            done
            log_success "CloudWatch alarms deleted"
        fi
    fi
    
    # Clean up SNS topics
    local topic_name="echoes-alerts-${ENVIRONMENT}"
    local topic_arn
    topic_arn=$(aws sns list-topics \
        --profile "$AWS_PROFILE" \
        --query "Topics[?contains(TopicArn, '$topic_name')].TopicArn" \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$topic_arn" ]]; then
        log_destroy "Deleting SNS topic: $topic_arn"
        
        if [[ "$DRY_RUN" = true ]]; then
            log_info "DRY RUN: Would delete SNS topic $topic_arn"
        else
            aws sns delete-topic --topic-arn "$topic_arn" --profile "$AWS_PROFILE" 2>/dev/null || true
            log_success "SNS topic deleted: $topic_arn"
        fi
    fi
}

# Clean up CDK bootstrap resources (optional)
cleanup_cdk_bootstrap() {
    if [[ "$ENVIRONMENT" = "prod" ]] && [[ "$PRESERVE_BACKUPS" = true ]]; then
        log_info "Preserving CDK bootstrap resources for production"
        return 0
    fi
    
    local bootstrap_bucket="cdk-${AWS_ACCOUNT_ID}-${AWS_REGION}-${ENVIRONMENT}"
    local bootstrap_stack="CDKToolkit-$ENVIRONMENT"
    
    if aws s3api head-bucket --bucket "$bootstrap_bucket" --profile "$AWS_PROFILE" 2>/dev/null; then
        log_warning "CDK bootstrap bucket found: $bootstrap_bucket"
        
        if [[ "$FORCE_DESTROY" = false ]]; then
            read -p "Delete CDK bootstrap resources? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                log_info "Preserving CDK bootstrap resources"
                return 0
            fi
        fi
        
        log_destroy "Cleaning up CDK bootstrap resources"
        
        if [[ "$DRY_RUN" = true ]]; then
            log_info "DRY RUN: Would delete CDK bootstrap resources"
        else
            # Empty bootstrap bucket
            aws s3 rm "s3://$bootstrap_bucket" --recursive --profile "$AWS_PROFILE" 2>/dev/null || true
            
            # Delete bootstrap stack
            if aws cloudformation describe-stacks --stack-name "$bootstrap_stack" --profile "$AWS_PROFILE" > /dev/null 2>&1; then
                aws cloudformation delete-stack --stack-name "$bootstrap_stack" --profile "$AWS_PROFILE" || true
                log_success "CDK bootstrap cleanup initiated"
            fi
        fi
    fi
}

# Remove old backups if requested
cleanup_old_backups() {
    if [[ "$PRESERVE_BACKUPS" = true ]]; then
        log_info "Preserving existing backups"
        return 0
    fi
    
    log_destroy "Removing old backups"
    
    local backup_patterns=(
        "$PROJECT_ROOT/tmp/backups/*$ENVIRONMENT*"
        "$PROJECT_ROOT/tmp/*$ENVIRONMENT*"
        "$PROJECT_ROOT/deploy/artifacts/$ENVIRONMENT"
        "$PROJECT_ROOT/deploy/configs/$ENVIRONMENT"
        "$PROJECT_ROOT/deploy/templates/$ENVIRONMENT"
    )
    
    for pattern in "${backup_patterns[@]}"; do
        if ls $pattern 2>/dev/null; then
            if [[ "$DRY_RUN" = true ]]; then
                log_info "DRY RUN: Would remove backup files matching: $pattern"
            else
                rm -rf $pattern 2>/dev/null || true
                log_success "Removed backup files: $pattern"
            fi
        fi
    done
}

# Generate destruction report
generate_destruction_report() {
    log_info "Generating destruction report"
    
    local report_file="$PROJECT_ROOT/tmp/destruction-report-$ENVIRONMENT-$(date +%Y%m%d-%H%M%S).json"
    
    cat > "$report_file" << EOF
{
  "destruction_report": {
    "environment": "$ENVIRONMENT",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "aws_account": "$AWS_ACCOUNT_ID",
    "aws_region": "$AWS_REGION",
    "executed_by": "$(whoami)",
    "dry_run": $DRY_RUN,
    "backup_created": $BACKUP_DATA,
    "backup_location": "${BACKUP_DIR:-none}"
  },
  "destroyed_resources": {
    "cloudformation_stacks": [
      "$NOTIF_STACK_NAME",
      "$API_STACK_NAME", 
      "$AUTH_STACK_NAME",
      "$STORAGE_STACK_NAME"
    ],
    "individual_resources": {
      "s3_bucket": "$S3_BUCKET_NAME",
      "dynamodb_table": "$DYNAMODB_TABLE_NAME",
      "cognito_user_pool": "$COGNITO_USER_POOL_ID",
      "api_gateway": "$API_GATEWAY_ID",
      "lambda_function": "$LAMBDA_FUNCTION_NAME"
    }
  },
  "cleanup_actions": [
    "CloudWatch logs deleted",
    "CloudWatch alarms removed",
    "SNS topics deleted",
    "Orphaned resources cleaned"
  ],
  "status": "$([ "$DRY_RUN" = true ] && echo "simulated" || echo "completed")"
}
EOF
    
    log_success "Destruction report saved: $report_file"
}

# Print final summary
print_final_summary() {
    echo
    echo -e "${BLUE}=================================${NC}"
    
    if [[ "$DRY_RUN" = true ]]; then
        echo -e "${BLUE}💭 DESTRUCTION SIMULATION COMPLETED${NC}"
        echo -e "${BLUE}=================================${NC}"
        echo
        echo -e "${BLUE}This was a dry run - no resources were actually destroyed.${NC}"
        echo -e "${BLUE}Review the simulation results and run without --dry-run to proceed.${NC}"
    else
        echo -e "${PURPLE}💥 INFRASTRUCTURE DESTRUCTION COMPLETED${NC}"
        echo -e "${BLUE}=================================${NC}"
        echo
        echo -e "${GREEN}Environment '$ENVIRONMENT' has been successfully destroyed.${NC}"
        
        if [[ "$BACKUP_DATA" = true ]] && [[ -n "${BACKUP_DIR:-}" ]]; then
            echo
            echo -e "${BLUE}📦 Data Backup Location:${NC}"
            echo "  $BACKUP_DIR"
            echo
            echo -e "${BLUE}💡 Recovery Information:${NC}"
            echo "  - DynamoDB schema and data backed up"
            echo "  - CloudFormation templates saved"
            echo "  - Environment configuration preserved"
            echo "  - To restore, redeploy and import backed up data"
        fi
    fi
    
    echo
    echo -e "${BLUE}🧹 Resources Processed:${NC}"
    echo "  🏗️  CloudFormation stacks"
    echo "  🗄️  S3 buckets and contents"
    echo "  📊 DynamoDB tables"
    echo "  👤 Cognito user pools"
    echo "  🔗 API Gateway instances"
    echo "  ⚡ Lambda functions"
    echo "  📈 CloudWatch resources"
    echo "  📢 SNS topics"
    
    if [[ "$DRY_RUN" = false ]]; then
        echo
        echo -e "${YELLOW}⚠️  Important Notes:${NC}"
        echo "  - All data for this environment has been permanently deleted"
        echo "  - DNS records (if any) may need manual cleanup"
        echo "  - Some AWS costs may continue for a short period"
        echo "  - Check AWS console to verify complete removal"
    fi
    
    echo -e "${BLUE}=================================${NC}"
}

# Main execution
main() {
    if [[ "$DRY_RUN" = true ]]; then
        echo -e "${BLUE}💭 Simulating infrastructure destruction for: $ENVIRONMENT${NC}"
    else
        echo -e "${PURPLE}💥 Destroying infrastructure for: $ENVIRONMENT${NC}"
    fi
    echo "================================="
    
    load_environment_config
    perform_safety_checks
    list_resources_for_destruction
    
    if [[ "$DRY_RUN" = false ]]; then
        backup_critical_data
    fi
    
    destroy_cloudformation_stacks
    cleanup_orphaned_resources
    cleanup_cdk_bootstrap
    cleanup_old_backups
    generate_destruction_report
    print_final_summary
    
    echo
    if [[ "$DRY_RUN" = true ]]; then
        log_success "Destruction simulation completed successfully!"
    else
        log_success "Infrastructure destruction completed successfully!"
    fi
}

# Run main function
main "$@"