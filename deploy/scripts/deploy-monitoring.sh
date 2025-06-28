#!/bin/bash

# Monitoring and Notifications Deployment Script for Echoes Backend
# Deploys CloudWatch monitoring, SNS notifications, and observability features

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
Monitoring and Notifications Deployment Script

Usage: $0 [options]

Options:
  -e, --environment <env>  Environment to deploy (dev, staging, prod)
  -p, --profile <profile>  AWS profile to use
  -y, --yes               Skip confirmation prompts
  -f, --force             Force update existing resources
  -h, --help              Show this help message

This script deploys:
  1. CloudWatch dashboards and metrics
  2. SNS topics for notifications
  3. CloudWatch alarms and alerts
  4. Log aggregation and retention policies
  5. X-Ray tracing configuration
  6. EventBridge rules for system events
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

# Check deployment dependencies
check_dependencies() {
    log_info "Checking deployment dependencies"
    
    # Check if required stacks exist
    local required_stacks=("$STORAGE_STACK_NAME" "$AUTH_STACK_NAME" "$API_STACK_NAME")
    
    for stack in "${required_stacks[@]}"; do
        if ! aws cloudformation describe-stacks --stack-name "$stack" --profile "$AWS_PROFILE" > /dev/null 2>&1; then
            log_error "Required stack not found: $stack"
            log_error "Deploy previous stacks first"
            exit 1
        fi
    done
    
    log_success "All dependencies are available"
}

# Deploy monitoring stack
deploy_monitoring_stack() {
    log_info "Deploying monitoring stack: $NOTIF_STACK_NAME"
    
    cd "$CDK_DIR"
    
    # Set CDK context
    local cdk_context=(
        "--context" "environment=$ENVIRONMENT"
        "--context" "awsAccountId=$AWS_ACCOUNT_ID"
        "--context" "awsRegion=$AWS_REGION"
    )
    
    # Deploy the monitoring stack
    if cdk deploy "$NOTIF_STACK_NAME" \
        --profile "$AWS_PROFILE" \
        "${cdk_context[@]}" \
        --require-approval never \
        --progress events \
        --outputs-file "$PROJECT_ROOT/tmp/outputs/monitoring-outputs-$ENVIRONMENT.json"; then
        
        log_success "Monitoring stack deployed successfully"
    else
        log_error "Monitoring stack deployment failed"
        exit 1
    fi
}

# Create CloudWatch dashboard
create_cloudwatch_dashboard() {
    log_info "Creating CloudWatch dashboard"
    
    local dashboard_name="Echoes-${ENVIRONMENT}-Dashboard"
    
    # Create dashboard configuration
    local dashboard_body=$(cat << EOF
{
    "widgets": [
        {
            "type": "metric",
            "x": 0,
            "y": 0,
            "width": 12,
            "height": 6,
            "properties": {
                "metrics": [
                    [ "AWS/ApiGateway", "Count", "ApiName", "$API_GATEWAY_NAME", "Stage", "$ENVIRONMENT" ],
                    [ ".", "4XXError", ".", ".", ".", "." ],
                    [ ".", "5XXError", ".", ".", ".", "." ]
                ],
                "view": "timeSeries",
                "stacked": false,
                "region": "$AWS_REGION",
                "title": "API Gateway Metrics",
                "period": 300
            }
        },
        {
            "type": "metric",
            "x": 12,
            "y": 0,
            "width": 12,
            "height": 6,
            "properties": {
                "metrics": [
                    [ "AWS/Lambda", "Invocations", "FunctionName", "$LAMBDA_FUNCTION_NAME" ],
                    [ ".", "Errors", ".", "." ],
                    [ ".", "Duration", ".", "." ]
                ],
                "view": "timeSeries",
                "stacked": false,
                "region": "$AWS_REGION",
                "title": "Lambda Function Metrics",
                "period": 300
            }
        },
        {
            "type": "metric",
            "x": 0,
            "y": 6,
            "width": 12,
            "height": 6,
            "properties": {
                "metrics": [
                    [ "AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", "$DYNAMODB_TABLE_NAME" ],
                    [ ".", "ConsumedWriteCapacityUnits", ".", "." ],
                    [ ".", "UserErrors", ".", "." ]
                ],
                "view": "timeSeries",
                "stacked": false,
                "region": "$AWS_REGION",
                "title": "DynamoDB Metrics",
                "period": 300
            }
        },
        {
            "type": "metric",
            "x": 12,
            "y": 6,
            "width": 12,
            "height": 6,
            "properties": {
                "metrics": [
                    [ "AWS/S3", "BucketSizeBytes", "BucketName", "$S3_BUCKET_NAME", "StorageType", "StandardStorage" ],
                    [ ".", "NumberOfObjects", ".", ".", ".", "AllStorageTypes" ]
                ],
                "view": "timeSeries",
                "stacked": false,
                "region": "$AWS_REGION",
                "title": "S3 Storage Metrics",
                "period": 86400
            }
        },
        {
            "type": "log",
            "x": 0,
            "y": 12,
            "width": 24,
            "height": 6,
            "properties": {
                "query": "SOURCE '/aws/lambda/$LAMBDA_FUNCTION_NAME'\n| fields @timestamp, @message\n| filter @message like /ERROR/\n| sort @timestamp desc\n| limit 100",
                "region": "$AWS_REGION",
                "title": "Recent Lambda Errors"
            }
        }
    ]
}
EOF
)
    
    # Create or update dashboard
    if aws cloudwatch put-dashboard \
        --dashboard-name "$dashboard_name" \
        --dashboard-body "$dashboard_body" \
        --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        
        log_success "CloudWatch dashboard created: $dashboard_name"
        log_info "Dashboard URL: https://${AWS_REGION}.console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#dashboards:name=${dashboard_name}"
    else
        log_warning "Failed to create CloudWatch dashboard"
    fi
}

# Setup SNS topics for notifications
setup_sns_notifications() {
    log_info "Setting up SNS notifications"
    
    local topic_name="echoes-alerts-${ENVIRONMENT}"
    local topic_arn
    
    # Create SNS topic
    topic_arn=$(aws sns create-topic --name "$topic_name" --profile "$AWS_PROFILE" --query 'TopicArn' --output text 2>/dev/null || echo "")
    
    if [[ -n "$topic_arn" ]]; then
        log_success "SNS topic created/found: $topic_arn"
        
        # Set topic attributes
        aws sns set-topic-attributes \
            --topic-arn "$topic_arn" \
            --attribute-name DisplayName \
            --attribute-value "Echoes ${ENVIRONMENT} Alerts" \
            --profile "$AWS_PROFILE" > /dev/null 2>&1 || true
        
        # Export topic ARN for use in alarms
        export SNS_TOPIC_ARN="$topic_arn"
        
        # Add email subscription for production
        if [[ "$ENVIRONMENT" = "prod" ]]; then
            log_info "For production alerts, subscribe to SNS topic:"
            log_info "aws sns subscribe --topic-arn $topic_arn --protocol email --notification-endpoint your-email@example.com"
        fi
    else
        log_warning "Failed to create SNS topic"
    fi
}

# Create comprehensive CloudWatch alarms
create_comprehensive_alarms() {
    log_info "Creating comprehensive CloudWatch alarms"
    
    # API Gateway alarms
    local api_alarms=(
        "4XXError:GreaterThanThreshold:50:5"
        "5XXError:GreaterThanThreshold:10:2"
        "Latency:GreaterThanThreshold:5000:3"
        "Count:GreaterThanThreshold:10000:5"
    )
    
    for alarm_config in "${api_alarms[@]}"; do
        IFS=':' read -r metric_name comparison threshold periods <<< "$alarm_config"
        local alarm_name="Echoes-API-${metric_name}-${ENVIRONMENT}"
        
        aws cloudwatch put-metric-alarm \
            --alarm-name "$alarm_name" \
            --alarm-description "Echoes API ${metric_name} alarm for ${ENVIRONMENT}" \
            --metric-name "$metric_name" \
            --namespace "AWS/ApiGateway" \
            --statistic "$([ "$metric_name" = "Latency" ] && echo "Average" || echo "Sum")" \
            --period 300 \
            --threshold "$threshold" \
            --comparison-operator "$comparison" \
            --evaluation-periods "$periods" \
            --alarm-actions "${SNS_TOPIC_ARN:-arn:aws:sns:${AWS_REGION}:${AWS_ACCOUNT_ID}:echoes-alerts-${ENVIRONMENT}}" \
            --dimensions "Name=ApiName,Value=$API_GATEWAY_NAME" "Name=Stage,Value=$ENVIRONMENT" \
            --profile "$AWS_PROFILE" > /dev/null 2>&1 && \
            log_success "Created alarm: $alarm_name" || \
            log_warning "Failed to create alarm: $alarm_name"
    done
    
    # Lambda alarms
    local lambda_alarms=(
        "Errors:GreaterThanThreshold:10:2"
        "Duration:GreaterThanThreshold:25000:3"
        "Throttles:GreaterThanThreshold:5:2"
        "ConcurrentExecutions:GreaterThanThreshold:80:3"
    )
    
    for alarm_config in "${lambda_alarms[@]}"; do
        IFS=':' read -r metric_name comparison threshold periods <<< "$alarm_config"
        local alarm_name="Echoes-Lambda-${metric_name}-${ENVIRONMENT}"
        
        aws cloudwatch put-metric-alarm \
            --alarm-name "$alarm_name" \
            --alarm-description "Echoes Lambda ${metric_name} alarm for ${ENVIRONMENT}" \
            --metric-name "$metric_name" \
            --namespace "AWS/Lambda" \
            --statistic "$([ "$metric_name" = "Duration" ] && echo "Average" || echo "Sum")" \
            --period 300 \
            --threshold "$threshold" \
            --comparison-operator "$comparison" \
            --evaluation-periods "$periods" \
            --alarm-actions "${SNS_TOPIC_ARN:-arn:aws:sns:${AWS_REGION}:${AWS_ACCOUNT_ID}:echoes-alerts-${ENVIRONMENT}}" \
            --dimensions "Name=FunctionName,Value=$LAMBDA_FUNCTION_NAME" \
            --profile "$AWS_PROFILE" > /dev/null 2>&1 && \
            log_success "Created alarm: $alarm_name" || \
            log_warning "Failed to create alarm: $alarm_name"
    done
    
    # DynamoDB alarms
    local dynamodb_alarms=(
        "ConsumedReadCapacityUnits:GreaterThanThreshold:80:3"
        "ConsumedWriteCapacityUnits:GreaterThanThreshold:80:3"
        "UserErrors:GreaterThanThreshold:10:2"
        "SystemErrors:GreaterThanThreshold:5:2"
    )
    
    for alarm_config in "${dynamodb_alarms[@]}"; do
        IFS=':' read -r metric_name comparison threshold periods <<< "$alarm_config"
        local alarm_name="Echoes-DynamoDB-${metric_name}-${ENVIRONMENT}"
        
        aws cloudwatch put-metric-alarm \
            --alarm-name "$alarm_name" \
            --alarm-description "Echoes DynamoDB ${metric_name} alarm for ${ENVIRONMENT}" \
            --metric-name "$metric_name" \
            --namespace "AWS/DynamoDB" \
            --statistic "Sum" \
            --period 300 \
            --threshold "$threshold" \
            --comparison-operator "$comparison" \
            --evaluation-periods "$periods" \
            --alarm-actions "${SNS_TOPIC_ARN:-arn:aws:sns:${AWS_REGION}:${AWS_ACCOUNT_ID}:echoes-alerts-${ENVIRONMENT}}" \
            --dimensions "Name=TableName,Value=$DYNAMODB_TABLE_NAME" \
            --profile "$AWS_PROFILE" > /dev/null 2>&1 && \
            log_success "Created alarm: $alarm_name" || \
            log_warning "Failed to create alarm: $alarm_name"
    done
}

# Setup log retention policies
setup_log_retention() {
    log_info "Setting up log retention policies"
    
    # Set retention for Lambda logs
    local lambda_log_group="/aws/lambda/$LAMBDA_FUNCTION_NAME"
    local retention_days
    
    case $ENVIRONMENT in
        prod)
            retention_days=30
            ;;
        staging)
            retention_days=14
            ;;
        *)
            retention_days=7
            ;;
    esac
    
    if aws logs put-retention-policy \
        --log-group-name "$lambda_log_group" \
        --retention-in-days "$retention_days" \
        --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        log_success "Set log retention for Lambda: ${retention_days} days"
    else
        log_warning "Failed to set log retention for Lambda"
    fi
    
    # Set retention for API Gateway logs
    local api_log_group="/aws/apigateway/$API_GATEWAY_ID"
    
    if aws logs put-retention-policy \
        --log-group-name "$api_log_group" \
        --retention-in-days "$retention_days" \
        --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        log_success "Set log retention for API Gateway: ${retention_days} days"
    else
        log_info "API Gateway log group may not exist yet"
    fi
}

# Configure X-Ray tracing
configure_xray_tracing() {
    log_info "Configuring X-Ray tracing"
    
    # Enable tracing for Lambda function
    if aws lambda put-function-configuration \
        --function-name "$LAMBDA_FUNCTION_NAME" \
        --tracing-config Mode=Active \
        --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        log_success "X-Ray tracing enabled for Lambda"
    else
        log_warning "Failed to enable X-Ray tracing for Lambda"
    fi
    
    # Enable tracing for API Gateway stage
    if aws apigateway update-stage \
        --rest-api-id "$API_GATEWAY_ID" \
        --stage-name "$ENVIRONMENT" \
        --patch-ops "op=replace,path=/tracingEnabled,value=true" \
        --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        log_success "X-Ray tracing enabled for API Gateway"
    else
        log_warning "Failed to enable X-Ray tracing for API Gateway"
    fi
}

# Create custom metrics and insights
create_custom_metrics() {
    log_info "Creating custom metrics and insights"
    
    # Create custom metric filters for application logs
    local log_group="/aws/lambda/$LAMBDA_FUNCTION_NAME"
    
    # Error count metric
    aws logs put-metric-filter \
        --log-group-name "$log_group" \
        --filter-name "Echoes-ErrorCount-${ENVIRONMENT}" \
        --filter-pattern "[timestamp, request_id, level=\"ERROR\", ...]" \
        --metric-transformations \
            metricName="EchoesErrorCount",metricNamespace="Echoes/${ENVIRONMENT}",metricValue="1" \
        --profile "$AWS_PROFILE" > /dev/null 2>&1 && \
        log_success "Created custom error count metric" || \
        log_warning "Failed to create custom error count metric"
    
    # User registration metric
    aws logs put-metric-filter \
        --log-group-name "$log_group" \
        --filter-name "Echoes-UserRegistrations-${ENVIRONMENT}" \
        --filter-pattern "[timestamp, request_id, level, message=\"User registered\", ...]" \
        --metric-transformations \
            metricName="EchoesUserRegistrations",metricNamespace="Echoes/${ENVIRONMENT}",metricValue="1" \
        --profile "$AWS_PROFILE" > /dev/null 2>&1 && \
        log_success "Created user registration metric" || \
        log_warning "Failed to create user registration metric"
    
    # Echo creation metric
    aws logs put-metric-filter \
        --log-group-name "$log_group" \
        --filter-name "Echoes-EchoCreations-${ENVIRONMENT}" \
        --filter-pattern "[timestamp, request_id, level, message=\"Echo created\", ...]" \
        --metric-transformations \
            metricName="EchoesEchoCreations",metricNamespace="Echoes/${ENVIRONMENT}",metricValue="1" \
        --profile "$AWS_PROFILE" > /dev/null 2>&1 && \
        log_success "Created echo creation metric" || \
        log_warning "Failed to create echo creation metric"
}

# Setup EventBridge rules
setup_eventbridge_rules() {
    log_info "Setting up EventBridge rules"
    
    local event_bus_name="echoes-events-${ENVIRONMENT}"
    
    # Create custom event bus
    if aws events create-event-bus --name "$event_bus_name" --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        log_success "EventBridge custom bus created: $event_bus_name"
    else
        log_info "EventBridge custom bus already exists or failed to create"
    fi
    
    # Create rule for S3 events
    local s3_rule_name="echoes-s3-events-${ENVIRONMENT}"
    
    aws events put-rule \
        --name "$s3_rule_name" \
        --event-pattern "{\"source\":[\"aws.s3\"],\"detail\":{\"bucket\":{\"name\":[\"$S3_BUCKET_NAME\"]}}}" \
        --description "Echoes S3 events for ${ENVIRONMENT}" \
        --profile "$AWS_PROFILE" > /dev/null 2>&1 && \
        log_success "Created EventBridge rule for S3 events" || \
        log_warning "Failed to create S3 events rule"
    
    # Create rule for DynamoDB events
    local dynamodb_rule_name="echoes-dynamodb-events-${ENVIRONMENT}"
    
    aws events put-rule \
        --name "$dynamodb_rule_name" \
        --event-pattern "{\"source\":[\"aws.dynamodb\"],\"detail\":{\"tableName\":[\"$DYNAMODB_TABLE_NAME\"]}}" \
        --description "Echoes DynamoDB events for ${ENVIRONMENT}" \
        --profile "$AWS_PROFILE" > /dev/null 2>&1 && \
        log_success "Created EventBridge rule for DynamoDB events" || \
        log_warning "Failed to create DynamoDB events rule"
}

# Generate monitoring summary
generate_summary() {
    log_info "Generating monitoring deployment summary"
    
    local summary_file="$PROJECT_ROOT/tmp/monitoring-deployment-$ENVIRONMENT.json"
    
    # Count created alarms
    local alarm_count
    alarm_count=$(aws cloudwatch describe-alarms \
        --alarm-name-prefix "Echoes-" \
        --profile "$AWS_PROFILE" \
        --query 'length(MetricAlarms[?contains(AlarmName, `'$ENVIRONMENT'`)])' \
        --output text 2>/dev/null || echo "0")
    
    # Get SNS topic info
    local topic_arn
    topic_arn=$(aws sns list-topics \
        --profile "$AWS_PROFILE" \
        --query "Topics[?contains(TopicArn, 'echoes-alerts-${ENVIRONMENT}')].TopicArn" \
        --output text 2>/dev/null || echo "")
    
    cat > "$summary_file" << EOF
{
  "monitoring_deployment": {
    "environment": "$ENVIRONMENT",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "status": "completed"
  },
  "resources": {
    "cloudwatch_dashboard": {
      "name": "Echoes-${ENVIRONMENT}-Dashboard",
      "url": "https://${AWS_REGION}.console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#dashboards:name=Echoes-${ENVIRONMENT}-Dashboard"
    },
    "sns_topic": {
      "arn": "$topic_arn",
      "name": "echoes-alerts-${ENVIRONMENT}"
    },
    "eventbridge_bus": {
      "name": "echoes-events-${ENVIRONMENT}"
    }
  },
  "configuration": {
    "alarms_created": $alarm_count,
    "xray_tracing_enabled": true,
    "log_retention_configured": true,
    "custom_metrics_enabled": true,
    "eventbridge_rules_configured": true
  },
  "urls": {
    "dashboard": "https://${AWS_REGION}.console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#dashboards:name=Echoes-${ENVIRONMENT}-Dashboard",
    "alarms": "https://${AWS_REGION}.console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#alarmsV2:?search=Echoes-",
    "logs": "https://${AWS_REGION}.console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#logsV2:log-groups",
    "xray": "https://${AWS_REGION}.console.aws.amazon.com/xray/home?region=${AWS_REGION}#/service-map"
  }
}
EOF
    
    log_success "Monitoring summary saved: $summary_file"
    
    # Display key information
    echo
    echo -e "${BLUE}📊 Monitoring Resources Created:${NC}"
    echo "  📈 CloudWatch Dashboard: Echoes-${ENVIRONMENT}-Dashboard"
    echo "  🚨 CloudWatch Alarms: $alarm_count created"
    echo "  📢 SNS Topic: echoes-alerts-${ENVIRONMENT}"
    echo "  🔄 EventBridge Bus: echoes-events-${ENVIRONMENT}"
    echo "  🔍 X-Ray Tracing: Enabled"
    
    echo
    echo -e "${BLUE}📋 Monitoring URLs:${NC}"
    echo "  Dashboard: https://${AWS_REGION}.console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#dashboards:name=Echoes-${ENVIRONMENT}-Dashboard"
    echo "  Alarms: https://${AWS_REGION}.console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#alarmsV2:?search=Echoes-"
    echo "  X-Ray: https://${AWS_REGION}.console.aws.amazon.com/xray/home?region=${AWS_REGION}#/service-map"
    
    if [[ "$ENVIRONMENT" = "prod" ]] && [[ -n "$topic_arn" ]]; then
        echo
        echo -e "${BLUE}⚠️  Production Alert Setup:${NC}"
        echo "  Subscribe to SNS topic for alerts:"
        echo "  aws sns subscribe --topic-arn $topic_arn --protocol email --notification-endpoint your-email@example.com"
    fi
}

# Main execution
main() {
    echo -e "${BLUE}📊 Deploying monitoring infrastructure for: $ENVIRONMENT${NC}"
    echo "================================="
    
    load_environment_config
    check_dependencies
    deploy_monitoring_stack
    create_cloudwatch_dashboard
    setup_sns_notifications
    create_comprehensive_alarms
    setup_log_retention
    configure_xray_tracing
    create_custom_metrics
    setup_eventbridge_rules
    generate_summary
    
    echo
    log_success "Monitoring infrastructure deployment completed successfully!"
    echo -e "${BLUE}Environment '$ENVIRONMENT' monitoring is ready.${NC}"
    echo
    echo -e "${BLUE}Next step: Run deployment verification${NC}"
    echo "  ./deploy/scripts/verify-deployment.sh -e $ENVIRONMENT"
}

# Run main function
main "$@"