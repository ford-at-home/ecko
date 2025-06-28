#!/bin/bash

# Log Viewing Utility for Echoes Backend
# Easy access to CloudWatch logs for debugging and monitoring

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

# Default values
ENVIRONMENT="dev"
AWS_PROFILE="${AWS_PROFILE:-default}"
LOG_TYPE="lambda"
FOLLOW=false
LINES=50
START_TIME=""
END_TIME=""
FILTER_PATTERN=""

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
        -t|--type)
            LOG_TYPE="$2"
            shift 2
            ;;
        -f|--follow)
            FOLLOW=true
            shift
            ;;
        -n|--lines)
            LINES="$2"
            shift 2
            ;;
        --start)
            START_TIME="$2"
            shift 2
            ;;
        --end)
            END_TIME="$2"
            shift 2
            ;;
        --filter)
            FILTER_PATTERN="$2"
            shift 2
            ;;
        -h|--help)
            cat << EOF
Log Viewing Utility for Echoes Backend

Usage: $0 [options]

Options:
  -e, --environment <env>     Environment (dev, staging, prod)
  -p, --profile <profile>     AWS profile to use
  -t, --type <type>          Log type: lambda, api, errors, all
  -f, --follow               Follow logs in real-time
  -n, --lines <number>       Number of lines to show (default: 50)
  --start <time>             Start time (e.g., '1h ago', '2023-01-01T10:00:00')
  --end <time>               End time (e.g., 'now', '2023-01-01T11:00:00')
  --filter <pattern>         Filter pattern for log search
  -h, --help                 Show this help message

Log Types:
  lambda      Lambda function logs (default)
  api         API Gateway access logs
  errors      Error logs across all services
  dashboard   CloudWatch dashboard URL
  all         All available logs

Examples:
  $0 -e prod -t lambda -f           # Follow prod Lambda logs
  $0 -e dev --filter "ERROR"        # Show dev error logs
  $0 -e staging --start "1h ago"    # Show last hour of logs
  $0 -t dashboard                   # Open CloudWatch dashboard
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
    local env_file="$PROJECT_ROOT/environments/$ENVIRONMENT/.env.infrastructure"
    
    if [[ ! -f "$env_file" ]]; then
        log_error "Environment file not found: $env_file"
        exit 1
    fi
    
    # Load environment variables
    set -a
    source "$env_file"
    set +a
}

# Parse time parameters
parse_time() {
    local time_input="$1"
    
    case $time_input in
        "now")
            date -u +%s000
            ;;
        *"ago")
            local amount=$(echo "$time_input" | sed 's/\([0-9]*\).*/\1/')
            local unit=$(echo "$time_input" | sed 's/[0-9]*\([a-z]*\).*/\1/')
            
            case $unit in
                "m"|"min"|"minute"|"minutes")
                    date -u -d "$amount minutes ago" +%s000
                    ;;
                "h"|"hour"|"hours")
                    date -u -d "$amount hours ago" +%s000
                    ;;
                "d"|"day"|"days")
                    date -u -d "$amount days ago" +%s000
                    ;;
                *)
                    date -u -d "$time_input" +%s000 2>/dev/null || echo ""
                    ;;
            esac
            ;;
        *)
            date -u -d "$time_input" +%s000 2>/dev/null || echo ""
            ;;
    esac
}

# View Lambda function logs
view_lambda_logs() {
    local log_group="/aws/lambda/$LAMBDA_FUNCTION_NAME"
    
    log_info "Viewing Lambda logs: $log_group"
    
    if ! aws logs describe-log-groups --log-group-name-prefix "$log_group" --profile "$AWS_PROFILE" 2>/dev/null | grep -q "$log_group"; then
        log_error "Lambda log group not found: $log_group"
        return 1
    fi
    
    local cmd_args=(
        "--log-group-name" "$log_group"
        "--profile" "$AWS_PROFILE"
    )
    
    # Add time range if specified
    if [[ -n "$START_TIME" ]]; then
        local start_ms
        start_ms=$(parse_time "$START_TIME")
        if [[ -n "$start_ms" ]]; then
            cmd_args+=("--start-time" "$start_ms")
        fi
    fi
    
    if [[ -n "$END_TIME" ]]; then
        local end_ms
        end_ms=$(parse_time "$END_TIME")
        if [[ -n "$end_ms" ]]; then
            cmd_args+=("--end-time" "$end_ms")
        fi
    fi
    
    # Add filter pattern
    if [[ -n "$FILTER_PATTERN" ]]; then
        cmd_args+=("--filter-pattern" "$FILTER_PATTERN")
    fi
    
    if [[ "$FOLLOW" = true ]]; then
        # Use tail for following logs
        aws logs tail "${cmd_args[@]}" --follow
    else
        # Use filter-log-events for static logs
        aws logs filter-log-events "${cmd_args[@]}" \
            --query 'events[*].[timestamp,message]' \
            --output table | tail -n "+4" | head -n "$LINES"
    fi
}

# View API Gateway logs
view_api_logs() {
    local log_group="/aws/apigateway/$API_GATEWAY_ID"
    
    log_info "Viewing API Gateway logs: $log_group"
    
    if ! aws logs describe-log-groups --log-group-name-prefix "$log_group" --profile "$AWS_PROFILE" 2>/dev/null | grep -q "$log_group"; then
        log_warning "API Gateway log group not found: $log_group"
        log_info "API Gateway logging may not be enabled"
        return 1
    fi
    
    local cmd_args=(
        "--log-group-name" "$log_group"
        "--profile" "$AWS_PROFILE"
    )
    
    # Add time range if specified
    if [[ -n "$START_TIME" ]]; then
        local start_ms
        start_ms=$(parse_time "$START_TIME")
        if [[ -n "$start_ms" ]]; then
            cmd_args+=("--start-time" "$start_ms")
        fi
    fi
    
    if [[ -n "$END_TIME" ]]; then
        local end_ms
        end_ms=$(parse_time "$END_TIME")
        if [[ -n "$end_ms" ]]; then
            cmd_args+=("--end-time" "$end_ms")
        fi
    fi
    
    # Add filter pattern for API logs
    if [[ -n "$FILTER_PATTERN" ]]; then
        cmd_args+=("--filter-pattern" "$FILTER_PATTERN")
    else
        # Default API filter for errors
        cmd_args+=("--filter-pattern" "[timestamp, request_id, status_code >= 400]")
    fi
    
    if [[ "$FOLLOW" = true ]]; then
        aws logs tail "${cmd_args[@]}" --follow
    else
        aws logs filter-log-events "${cmd_args[@]}" \
            --query 'events[*].[timestamp,message]' \
            --output table | tail -n "+4" | head -n "$LINES"
    fi
}

# View error logs across all services
view_error_logs() {
    log_info "Searching for error logs across all services"
    
    local log_groups=(
        "/aws/lambda/$LAMBDA_FUNCTION_NAME"
        "/aws/apigateway/$API_GATEWAY_ID"
    )
    
    local error_patterns=(
        "ERROR"
        "Exception"
        "error"
        "failed"
        "timeout"
    )
    
    for log_group in "${log_groups[@]}"; do
        if aws logs describe-log-groups --log-group-name-prefix "$log_group" --profile "$AWS_PROFILE" 2>/dev/null | grep -q "$log_group"; then
            echo
            log_info "Errors in $log_group:"
            echo "----------------------------------------"
            
            for pattern in "${error_patterns[@]}"; do
                local cmd_args=(
                    "--log-group-name" "$log_group"
                    "--filter-pattern" "$pattern"
                    "--profile" "$AWS_PROFILE"
                    "--max-items" "10"
                )
                
                # Add time range if specified
                if [[ -n "$START_TIME" ]]; then
                    local start_ms
                    start_ms=$(parse_time "$START_TIME")
                    if [[ -n "$start_ms" ]]; then
                        cmd_args+=("--start-time" "$start_ms")
                    fi
                fi
                
                aws logs filter-log-events "${cmd_args[@]}" \
                    --query 'events[*].[timestamp,message]' \
                    --output table 2>/dev/null | tail -n "+4" | head -n 5
            done
        fi
    done
}

# Open CloudWatch dashboard
open_dashboard() {
    local dashboard_name="Echoes-${ENVIRONMENT}-Dashboard"
    local dashboard_url="https://${AWS_REGION}.console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#dashboards:name=${dashboard_name}"
    
    log_info "CloudWatch Dashboard URL:"
    echo "$dashboard_url"
    
    # Try to open in browser (macOS/Linux)
    if command -v open >/dev/null 2>&1; then
        open "$dashboard_url"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$dashboard_url"
    else
        log_info "Copy the URL above to open the dashboard in your browser"
    fi
}

# View all available logs
view_all_logs() {
    log_info "Available log groups for environment: $ENVIRONMENT"
    echo
    
    # List all log groups with our prefix
    local log_groups
    log_groups=$(aws logs describe-log-groups \
        --profile "$AWS_PROFILE" \
        --query 'logGroups[?contains(logGroupName, `echoes`) || contains(logGroupName, `Echoes`) || contains(logGroupName, `'$LAMBDA_FUNCTION_NAME'`) || contains(logGroupName, `'$API_GATEWAY_ID'`)].{Name:logGroupName,Size:storedBytes,Retention:retentionInDays}' \
        --output table 2>/dev/null || echo "")
    
    if [[ -n "$log_groups" ]]; then
        echo "$log_groups"
    else
        log_warning "No log groups found for this environment"
    fi
    
    echo
    log_info "Recent log streams:"
    
    # Show recent streams for Lambda logs
    local lambda_log_group="/aws/lambda/$LAMBDA_FUNCTION_NAME"
    if aws logs describe-log-groups --log-group-name-prefix "$lambda_log_group" --profile "$AWS_PROFILE" 2>/dev/null | grep -q "$lambda_log_group"; then
        echo
        echo "Lambda Log Streams:"
        aws logs describe-log-streams \
            --log-group-name "$lambda_log_group" \
            --order-by LastEventTime \
            --descending \
            --max-items 5 \
            --profile "$AWS_PROFILE" \
            --query 'logStreams[*].{Stream:logStreamName,LastEvent:lastEventTime,Size:storedBytes}' \
            --output table 2>/dev/null || true
    fi
}

# Display log statistics
show_log_stats() {
    log_info "Log statistics for environment: $ENVIRONMENT"
    
    local log_groups=(
        "/aws/lambda/$LAMBDA_FUNCTION_NAME"
        "/aws/apigateway/$API_GATEWAY_ID"
    )
    
    for log_group in "${log_groups[@]}"; do
        if aws logs describe-log-groups --log-group-name-prefix "$log_group" --profile "$AWS_PROFILE" 2>/dev/null | grep -q "$log_group"; then
            echo
            echo "Statistics for $log_group:"
            
            # Get log group info
            local log_info
            log_info=$(aws logs describe-log-groups \
                --log-group-name-prefix "$log_group" \
                --profile "$AWS_PROFILE" \
                --query 'logGroups[0].{StoredBytes:storedBytes,RetentionDays:retentionInDays,CreationTime:creationTime}' \
                --output json 2>/dev/null || echo "{}")
            
            local stored_bytes
            stored_bytes=$(echo "$log_info" | jq -r '.StoredBytes // 0')
            local retention_days
            retention_days=$(echo "$log_info" | jq -r '.RetentionDays // "Not set"')
            
            echo "  Storage: $(( stored_bytes / 1024 / 1024 )) MB"
            echo "  Retention: $retention_days days"
            
            # Count recent log events
            local recent_events
            recent_events=$(aws logs filter-log-events \
                --log-group-name "$log_group" \
                --start-time "$(($(date +%s) - 3600))000" \
                --profile "$AWS_PROFILE" \
                --query 'length(events)' \
                --output text 2>/dev/null || echo "0")
            
            echo "  Recent events (last hour): $recent_events"
        fi
    done
}

# Main execution
main() {
    echo -e "${BLUE}📄 Echoes Log Viewer - Environment: $ENVIRONMENT${NC}"
    echo "================================="
    
    load_environment_config
    
    case $LOG_TYPE in
        "lambda")
            view_lambda_logs
            ;;
        "api")
            view_api_logs
            ;;
        "errors")
            view_error_logs
            ;;
        "dashboard")
            open_dashboard
            ;;
        "all")
            view_all_logs
            show_log_stats
            ;;
        "stats")
            show_log_stats
            ;;
        *)
            log_error "Unknown log type: $LOG_TYPE"
            log_info "Available types: lambda, api, errors, dashboard, all, stats"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"