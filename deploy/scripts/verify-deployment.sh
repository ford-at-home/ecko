#!/bin/bash

# Deployment Verification Script for Echoes Backend
# Comprehensive testing and validation of deployed infrastructure

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

# Default values
ENVIRONMENT="dev"
AWS_PROFILE="${AWS_PROFILE:-default}"
COMPREHENSIVE=false
SKIP_PERFORMANCE=false
GENERATE_REPORT=true

# Test results tracking
declare -A test_results
total_tests=0
passed_tests=0
failed_tests=0

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
        -c|--comprehensive)
            COMPREHENSIVE=true
            shift
            ;;
        --skip-performance)
            SKIP_PERFORMANCE=true
            shift
            ;;
        --no-report)
            GENERATE_REPORT=false
            shift
            ;;
        -h|--help)
            cat << EOF
Deployment Verification Script

Usage: $0 [options]

Options:
  -e, --environment <env>  Environment to verify (dev, staging, prod)
  -p, --profile <profile>  AWS profile to use
  -c, --comprehensive     Run comprehensive tests including load testing
  --skip-performance      Skip performance tests
  --no-report            Don't generate verification report
  -h, --help             Show this help message

This script verifies:
  1. Infrastructure deployment status
  2. Service health and connectivity
  3. Authentication functionality
  4. API endpoint functionality
  5. Database operations
  6. Storage operations
  7. Monitoring and logging
  8. Security configurations
  9. Performance benchmarks (optional)
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

log_test_start() {
    echo -e "${PURPLE}🧪 Testing: $1${NC}"
}

# Test result tracking
record_test_result() {
    local test_name="$1"
    local result="$2"
    local details="${3:-}"
    
    ((total_tests++))
    
    if [[ "$result" = "PASS" ]]; then
        ((passed_tests++))
        test_results["$test_name"]="PASS:$details"
        log_success "$test_name: PASSED"
    else
        ((failed_tests++))
        test_results["$test_name"]="FAIL:$details"
        log_error "$test_name: FAILED - $details"
    fi
}

# Load environment configuration
load_environment_config() {
    log_info "Loading environment configuration"
    
    local env_file="$PROJECT_ROOT/environments/$ENVIRONMENT/.env.infrastructure"
    
    if [[ ! -f "$env_file" ]]; then
        log_error "Environment file not found: $env_file"
        exit 1
    fi
    
    # Load environment variables
    set -a
    source "$env_file"
    set +a
    
    log_success "Environment configuration loaded"
}

# Test CloudFormation stacks
test_cloudformation_stacks() {
    log_test_start "CloudFormation Stack Status"
    
    local stacks=("$STORAGE_STACK_NAME" "$AUTH_STACK_NAME" "$API_STACK_NAME" "$NOTIF_STACK_NAME")
    local stack_failures=0
    
    for stack in "${stacks[@]}"; do
        local stack_status
        stack_status=$(aws cloudformation describe-stacks \
            --stack-name "$stack" \
            --profile "$AWS_PROFILE" \
            --query 'Stacks[0].StackStatus' \
            --output text 2>/dev/null || echo "NOT_FOUND")
        
        if [[ "$stack_status" =~ ^(CREATE_COMPLETE|UPDATE_COMPLETE)$ ]]; then
            log_success "Stack $stack: $stack_status"
        else
            log_error "Stack $stack: $stack_status"
            ((stack_failures++))
        fi
    done
    
    if [[ $stack_failures -eq 0 ]]; then
        record_test_result "CloudFormation Stacks" "PASS" "All ${#stacks[@]} stacks are healthy"
    else
        record_test_result "CloudFormation Stacks" "FAIL" "$stack_failures stacks have issues"
    fi
}

# Test S3 bucket functionality
test_s3_functionality() {
    log_test_start "S3 Bucket Functionality"
    
    local test_key="verification-test-$(date +%s).txt"
    local test_content="Verification test at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    
    # Test bucket exists and is accessible
    if ! aws s3api head-bucket --bucket "$S3_BUCKET_NAME" --profile "$AWS_PROFILE" 2>/dev/null; then
        record_test_result "S3 Bucket Access" "FAIL" "Bucket not accessible: $S3_BUCKET_NAME"
        return 1
    fi
    
    # Test upload
    if echo "$test_content" | aws s3 cp - "s3://${S3_BUCKET_NAME}/verification/${test_key}" --profile "$AWS_PROFILE" 2>/dev/null; then
        log_success "S3 upload test passed"
        
        # Test download
        local downloaded_content
        downloaded_content=$(aws s3 cp "s3://${S3_BUCKET_NAME}/verification/${test_key}" - --profile "$AWS_PROFILE" 2>/dev/null || echo "")
        
        if [[ "$downloaded_content" = "$test_content" ]]; then
            log_success "S3 download test passed"
            
            # Test delete
            if aws s3 rm "s3://${S3_BUCKET_NAME}/verification/${test_key}" --profile "$AWS_PROFILE" 2>/dev/null; then
                log_success "S3 delete test passed"
                record_test_result "S3 Functionality" "PASS" "Upload, download, and delete operations successful"
            else
                record_test_result "S3 Functionality" "FAIL" "Delete operation failed"
            fi
        else
            record_test_result "S3 Functionality" "FAIL" "Download verification failed"
        fi
    else
        record_test_result "S3 Functionality" "FAIL" "Upload operation failed"
    fi
    
    # Test CORS configuration
    local cors_config
    cors_config=$(aws s3api get-bucket-cors --bucket "$S3_BUCKET_NAME" --profile "$AWS_PROFILE" 2>/dev/null || echo "")
    
    if [[ -n "$cors_config" ]]; then
        log_success "S3 CORS configuration found"
    else
        log_warning "S3 CORS configuration not found"
    fi
}

# Test DynamoDB functionality
test_dynamodb_functionality() {
    log_test_start "DynamoDB Table Functionality"
    
    # Test table exists and is active
    local table_status
    table_status=$(aws dynamodb describe-table \
        --table-name "$DYNAMODB_TABLE_NAME" \
        --profile "$AWS_PROFILE" \
        --query 'Table.TableStatus' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    
    if [[ "$table_status" != "ACTIVE" ]]; then
        record_test_result "DynamoDB Table Status" "FAIL" "Table status: $table_status"
        return 1
    fi
    
    # Test write operation
    local test_user_id="verification-user-$(date +%s)"
    local test_echo_id="verification-echo-$(date +%s)"
    
    local test_item=$(cat << EOF
{
    "userId": {"S": "$test_user_id"},
    "echoId": {"S": "$test_echo_id"},
    "timestamp": {"S": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"},
    "itemType": {"S": "VERIFICATION_TEST"},
    "status": {"S": "ACTIVE"}
}
EOF
)
    
    if aws dynamodb put-item \
        --table-name "$DYNAMODB_TABLE_NAME" \
        --item "$test_item" \
        --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        
        log_success "DynamoDB write test passed"
        
        # Test read operation
        if aws dynamodb get-item \
            --table-name "$DYNAMODB_TABLE_NAME" \
            --key "{\"userId\":{\"S\":\"$test_user_id\"},\"echoId\":{\"S\":\"$test_echo_id\"}}" \
            --profile "$AWS_PROFILE" > /dev/null 2>&1; then
            
            log_success "DynamoDB read test passed"
            
            # Test delete operation
            if aws dynamodb delete-item \
                --table-name "$DYNAMODB_TABLE_NAME" \
                --key "{\"userId\":{\"S\":\"$test_user_id\"},\"echoId\":{\"S\":\"$test_echo_id\"}}" \
                --profile "$AWS_PROFILE" > /dev/null 2>&1; then
                
                log_success "DynamoDB delete test passed"
                record_test_result "DynamoDB Functionality" "PASS" "CRUD operations successful"
            else
                record_test_result "DynamoDB Functionality" "FAIL" "Delete operation failed"
            fi
        else
            record_test_result "DynamoDB Functionality" "FAIL" "Read operation failed"
        fi
    else
        record_test_result "DynamoDB Functionality" "FAIL" "Write operation failed"
    fi
    
    # Test GSI functionality
    if aws dynamodb query \
        --table-name "$DYNAMODB_TABLE_NAME" \
        --index-name "emotion-timestamp-index" \
        --key-condition-expression "emotion = :emotion" \
        --expression-attribute-values '{":emotion":{"S":"happy"}}' \
        --limit 1 \
        --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        log_success "DynamoDB GSI test passed"
    else
        log_warning "DynamoDB GSI test failed"
    fi
}

# Test Cognito authentication
test_cognito_authentication() {
    log_test_start "Cognito Authentication"
    
    # Test User Pool exists
    local user_pool_info
    user_pool_info=$(aws cognito-idp describe-user-pool \
        --user-pool-id "$COGNITO_USER_POOL_ID" \
        --profile "$AWS_PROFILE" \
        --output json 2>/dev/null || echo "{}")
    
    if [[ "$(echo "$user_pool_info" | jq -r '.UserPool.Id // empty')" = "$COGNITO_USER_POOL_ID" ]]; then
        log_success "Cognito User Pool accessible"
        
        # Test User Pool Client
        local client_info
        client_info=$(aws cognito-idp describe-user-pool-client \
            --user-pool-id "$COGNITO_USER_POOL_ID" \
            --client-id "$COGNITO_USER_POOL_CLIENT_ID" \
            --profile "$AWS_PROFILE" \
            --output json 2>/dev/null || echo "{}")
        
        if [[ "$(echo "$client_info" | jq -r '.UserPoolClient.ClientId // empty')" = "$COGNITO_USER_POOL_CLIENT_ID" ]]; then
            log_success "Cognito User Pool Client accessible"
            
            # Test authentication flow with test user (non-prod only)
            if [[ "$ENVIRONMENT" != "prod" ]]; then
                local test_username="testuser"
                local test_password="TestPassword123!"
                
                local auth_result
                auth_result=$(aws cognito-idp admin-initiate-auth \
                    --user-pool-id "$COGNITO_USER_POOL_ID" \
                    --client-id "$COGNITO_USER_POOL_CLIENT_ID" \
                    --auth-flow ADMIN_NO_SRP_AUTH \
                    --auth-parameters USERNAME="$test_username",PASSWORD="$test_password" \
                    --profile "$AWS_PROFILE" \
                    --output json 2>/dev/null || echo "{}")
                
                if [[ "$(echo "$auth_result" | jq -r '.AuthenticationResult.AccessToken // empty')" != "" ]]; then
                    log_success "Cognito authentication test passed"
                    record_test_result "Cognito Authentication" "PASS" "User Pool, Client, and authentication flow working"
                else
                    record_test_result "Cognito Authentication" "FAIL" "Authentication flow failed"
                fi
            else
                record_test_result "Cognito Authentication" "PASS" "User Pool and Client configuration verified"
            fi
        else
            record_test_result "Cognito Authentication" "FAIL" "User Pool Client not accessible"
        fi
    else
        record_test_result "Cognito Authentication" "FAIL" "User Pool not accessible"
    fi
}

# Test API Gateway endpoints
test_api_endpoints() {
    log_test_start "API Gateway Endpoints"
    
    local endpoint_failures=0
    
    # Test health endpoint
    log_info "Testing health endpoint: ${API_GATEWAY_URL}/health"
    local health_response
    health_response=$(curl -s -w "%{http_code}" -o /tmp/health_response.json "${API_GATEWAY_URL}/health" 2>/dev/null || echo "000")
    
    if [[ "$health_response" = "200" ]]; then
        local health_status
        health_status=$(jq -r '.status // "unknown"' /tmp/health_response.json 2>/dev/null || echo "unknown")
        log_success "Health endpoint: HTTP $health_response, Status: $health_status"
    else
        log_error "Health endpoint: HTTP $health_response"
        ((endpoint_failures++))
    fi
    
    # Test root endpoint
    log_info "Testing root endpoint: ${API_GATEWAY_URL}/"
    local root_response
    root_response=$(curl -s -w "%{http_code}" -o /tmp/root_response.json "${API_GATEWAY_URL}/" 2>/dev/null || echo "000")
    
    if [[ "$root_response" = "200" ]]; then
        log_success "Root endpoint: HTTP $root_response"
    else
        log_error "Root endpoint: HTTP $root_response"
        ((endpoint_failures++))
    fi
    
    # Test CORS preflight
    log_info "Testing CORS preflight"
    local cors_response
    cors_response=$(curl -s -I \
        -H "Origin: https://example.com" \
        -H "Access-Control-Request-Method: POST" \
        -H "Access-Control-Request-Headers: Content-Type,Authorization" \
        -X OPTIONS "${API_GATEWAY_URL}/health" 2>/dev/null || echo "")
    
    if echo "$cors_response" | grep -q "Access-Control-Allow-Origin"; then
        log_success "CORS preflight: Headers present"
    else
        log_warning "CORS preflight: Headers missing"
        ((endpoint_failures++))
    fi
    
    # Test authenticated endpoint (if test user exists)
    if [[ "$ENVIRONMENT" != "prod" ]]; then
        log_info "Testing authenticated endpoint"
        
        # Try to get auth token first
        local auth_token=""
        if [[ -n "$COGNITO_USER_POOL_ID" ]] && [[ -n "$COGNITO_USER_POOL_CLIENT_ID" ]]; then
            local auth_result
            auth_result=$(aws cognito-idp admin-initiate-auth \
                --user-pool-id "$COGNITO_USER_POOL_ID" \
                --client-id "$COGNITO_USER_POOL_CLIENT_ID" \
                --auth-flow ADMIN_NO_SRP_AUTH \
                --auth-parameters USERNAME="testuser",PASSWORD="TestPassword123!" \
                --profile "$AWS_PROFILE" \
                --output json 2>/dev/null || echo "{}")
            
            auth_token=$(echo "$auth_result" | jq -r '.AuthenticationResult.AccessToken // empty')
        fi
        
        if [[ -n "$auth_token" ]]; then
            local echoes_response
            echoes_response=$(curl -s -w "%{http_code}" \
                -H "Authorization: Bearer $auth_token" \
                -o /tmp/echoes_response.json \
                "${API_GATEWAY_URL}/echoes" 2>/dev/null || echo "000")
            
            if [[ "$echoes_response" =~ ^(200|401)$ ]]; then
                log_success "Authenticated endpoint: HTTP $echoes_response (auth working)"
            else
                log_warning "Authenticated endpoint: HTTP $echoes_response"
            fi
        else
            log_info "Skipping authenticated endpoint test (no auth token)"
        fi
    fi
    
    # Clean up temp files
    rm -f /tmp/health_response.json /tmp/root_response.json /tmp/echoes_response.json
    
    if [[ $endpoint_failures -eq 0 ]]; then
        record_test_result "API Endpoints" "PASS" "All endpoint tests passed"
    else
        record_test_result "API Endpoints" "FAIL" "$endpoint_failures endpoint tests failed"
    fi
}

# Test Lambda function
test_lambda_function() {
    log_test_start "Lambda Function"
    
    # Test function exists and is active
    local function_info
    function_info=$(aws lambda get-function \
        --function-name "$LAMBDA_FUNCTION_NAME" \
        --profile "$AWS_PROFILE" \
        --output json 2>/dev/null || echo "{}")
    
    local function_state
    function_state=$(echo "$function_info" | jq -r '.Configuration.State // "NotFound"')
    
    if [[ "$function_state" = "Active" ]]; then
        log_success "Lambda function is active"
        
        # Test function invocation
        local invocation_result
        invocation_result=$(aws lambda invoke \
            --function-name "$LAMBDA_FUNCTION_NAME" \
            --payload '{"httpMethod":"GET","path":"/health","headers":{}}' \
            --profile "$AWS_PROFILE" \
            /tmp/lambda_response.json 2>/dev/null && echo "SUCCESS" || echo "FAILED")
        
        if [[ "$invocation_result" = "SUCCESS" ]]; then
            local response_code
            response_code=$(jq -r '.statusCode // 0' /tmp/lambda_response.json 2>/dev/null || echo "0")
            
            if [[ "$response_code" = "200" ]]; then
                log_success "Lambda function invocation successful"
                record_test_result "Lambda Function" "PASS" "Function active and responding correctly"
            else
                record_test_result "Lambda Function" "FAIL" "Function returned status code: $response_code"
            fi
        else
            record_test_result "Lambda Function" "FAIL" "Function invocation failed"
        fi
        
        rm -f /tmp/lambda_response.json
    else
        record_test_result "Lambda Function" "FAIL" "Function state: $function_state"
    fi
}

# Test monitoring and logging
test_monitoring() {
    log_test_start "Monitoring and Logging"
    
    local monitoring_failures=0
    
    # Test CloudWatch dashboard exists
    local dashboard_name="Echoes-${ENVIRONMENT}-Dashboard"
    if aws cloudwatch get-dashboard --dashboard-name "$dashboard_name" --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        log_success "CloudWatch dashboard exists: $dashboard_name"
    else
        log_warning "CloudWatch dashboard not found: $dashboard_name"
        ((monitoring_failures++))
    fi
    
    # Test CloudWatch alarms
    local alarm_count
    alarm_count=$(aws cloudwatch describe-alarms \
        --alarm-name-prefix "Echoes-" \
        --profile "$AWS_PROFILE" \
        --query "length(MetricAlarms[?contains(AlarmName, '$ENVIRONMENT')])" \
        --output text 2>/dev/null || echo "0")
    
    if [[ $alarm_count -gt 0 ]]; then
        log_success "CloudWatch alarms found: $alarm_count"
    else
        log_warning "No CloudWatch alarms found for environment"
        ((monitoring_failures++))
    fi
    
    # Test Lambda logs
    local log_group="/aws/lambda/$LAMBDA_FUNCTION_NAME"
    if aws logs describe-log-groups --log-group-name-prefix "$log_group" --profile "$AWS_PROFILE" | grep -q "$log_group"; then
        log_success "Lambda log group exists"
        
        # Check for recent log entries
        local recent_logs
        recent_logs=$(aws logs describe-log-streams \
            --log-group-name "$log_group" \
            --order-by LastEventTime \
            --descending \
            --max-items 1 \
            --profile "$AWS_PROFILE" \
            --query 'logStreams[0].lastEventTime' \
            --output text 2>/dev/null || echo "0")
        
        if [[ $recent_logs -gt 0 ]]; then
            log_success "Recent log entries found"
        else
            log_warning "No recent log entries found"
        fi
    else
        log_warning "Lambda log group not found"
        ((monitoring_failures++))
    fi
    
    if [[ $monitoring_failures -eq 0 ]]; then
        record_test_result "Monitoring and Logging" "PASS" "Dashboard, alarms, and logs configured"
    else
        record_test_result "Monitoring and Logging" "FAIL" "$monitoring_failures monitoring components missing"
    fi
}

# Test security configurations
test_security() {
    log_test_start "Security Configurations"
    
    local security_issues=0
    
    # Test S3 bucket public access
    local public_access_config
    public_access_config=$(aws s3api get-public-access-block --bucket "$S3_BUCKET_NAME" --profile "$AWS_PROFILE" --output json 2>/dev/null || echo "{}")
    
    local block_public_acls
    block_public_acls=$(echo "$public_access_config" | jq -r '.PublicAccessBlockConfiguration.BlockPublicAcls // false')
    
    if [[ "$block_public_acls" = "true" ]]; then
        log_success "S3 bucket public access blocked"
    else
        log_warning "S3 bucket public access not fully blocked"
        ((security_issues++))
    fi
    
    # Test DynamoDB encryption
    local table_encryption
    table_encryption=$(aws dynamodb describe-table \
        --table-name "$DYNAMODB_TABLE_NAME" \
        --profile "$AWS_PROFILE" \
        --query 'Table.SSEDescription.Status' \
        --output text 2>/dev/null || echo "DISABLED")
    
    if [[ "$table_encryption" = "ENABLED" ]]; then
        log_success "DynamoDB encryption enabled"
    else
        log_warning "DynamoDB encryption status: $table_encryption"
        ((security_issues++))
    fi
    
    # Test Lambda function environment variables (no sensitive data)
    local lambda_env
    lambda_env=$(aws lambda get-function-configuration \
        --function-name "$LAMBDA_FUNCTION_NAME" \
        --profile "$AWS_PROFILE" \
        --query 'Environment.Variables' \
        --output json 2>/dev/null || echo "{}")
    
    if echo "$lambda_env" | jq -r 'keys[]' | grep -qE "(PASSWORD|SECRET|KEY)"; then
        log_warning "Lambda environment may contain sensitive variable names"
        ((security_issues++))
    else
        log_success "Lambda environment variables look secure"
    fi
    
    if [[ $security_issues -eq 0 ]]; then
        record_test_result "Security Configurations" "PASS" "Security best practices followed"
    else
        record_test_result "Security Configurations" "FAIL" "$security_issues security issues found"
    fi
}

# Performance tests (optional)
run_performance_tests() {
    if [[ "$SKIP_PERFORMANCE" = true ]]; then
        log_info "Skipping performance tests"
        return 0
    fi
    
    log_test_start "Performance Benchmarks"
    
    # Simple load test on health endpoint
    log_info "Running basic load test on health endpoint"
    
    local total_requests=50
    local concurrent_requests=5
    local success_count=0
    local total_time=0
    
    # Create temporary script for load testing
    cat > /tmp/load_test.sh << 'EOF'
#!/bin/bash
URL="$1"
for i in {1..10}; do
    start_time=$(date +%s%N)
    response=$(curl -s -w "%{http_code}" -o /dev/null "$URL" 2>/dev/null || echo "000")
    end_time=$(date +%s%N)
    duration=$(( (end_time - start_time) / 1000000 ))
    echo "$response:$duration"
done
EOF
    
    chmod +x /tmp/load_test.sh
    
    # Run concurrent requests
    local temp_results="/tmp/load_test_results_$$"
    for ((i=1; i<=concurrent_requests; i++)); do
        /tmp/load_test.sh "${API_GATEWAY_URL}/health" > "${temp_results}_$i" &
    done
    
    # Wait for all background jobs to complete
    wait
    
    # Analyze results
    for ((i=1; i<=concurrent_requests; i++)); do
        while IFS=':' read -r status_code duration; do
            if [[ "$status_code" = "200" ]]; then
                ((success_count++))
                total_time=$((total_time + duration))
            fi
        done < "${temp_results}_$i"
        rm -f "${temp_results}_$i"
    done
    
    rm -f /tmp/load_test.sh
    
    local success_rate=$((success_count * 100 / total_requests))
    local avg_response_time=$((success_count > 0 ? total_time / success_count : 0))
    
    log_info "Performance Results:"
    log_info "  Total Requests: $total_requests"
    log_info "  Successful Requests: $success_count"
    log_info "  Success Rate: ${success_rate}%"
    log_info "  Average Response Time: ${avg_response_time}ms"
    
    if [[ $success_rate -ge 95 ]] && [[ $avg_response_time -lt 2000 ]]; then
        record_test_result "Performance Benchmarks" "PASS" "Success rate: ${success_rate}%, Avg response: ${avg_response_time}ms"
    else
        record_test_result "Performance Benchmarks" "FAIL" "Success rate: ${success_rate}%, Avg response: ${avg_response_time}ms"
    fi
}

# Generate verification report
generate_verification_report() {
    if [[ "$GENERATE_REPORT" = false ]]; then
        return 0
    fi
    
    log_info "Generating verification report"
    
    local report_file="$PROJECT_ROOT/tmp/verification-report-$ENVIRONMENT.json"
    local timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    
    # Create report header
    cat > "$report_file" << EOF
{
  "verification_report": {
    "environment": "$ENVIRONMENT",
    "timestamp": "$timestamp",
    "total_tests": $total_tests,
    "passed_tests": $passed_tests,
    "failed_tests": $failed_tests,
    "success_rate": $(( passed_tests * 100 / total_tests ))
  },
  "test_results": {
EOF
    
    # Add test results
    local first=true
    for test_name in "${!test_results[@]}"; do
        if [[ "$first" = true ]]; then
            first=false
        else
            echo "," >> "$report_file"
        fi
        
        IFS=':' read -r result details <<< "${test_results[$test_name]}"
        echo "    \"$test_name\": {" >> "$report_file"
        echo "      \"result\": \"$result\"," >> "$report_file"
        echo "      \"details\": \"$details\"" >> "$report_file"
        echo -n "    }" >> "$report_file"
    done
    
    # Close JSON
    cat >> "$report_file" << EOF

  },
  "summary": {
    "deployment_status": "$([ $failed_tests -eq 0 ] && echo "HEALTHY" || echo "ISSUES_FOUND")",
    "critical_services": {
      "api_gateway": "$([ "${test_results[API Endpoints]:-}" =~ ^PASS ] && echo "HEALTHY" || echo "UNHEALTHY")",
      "lambda": "$([ "${test_results[Lambda Function]:-}" =~ ^PASS ] && echo "HEALTHY" || echo "UNHEALTHY")",
      "dynamodb": "$([ "${test_results[DynamoDB Functionality]:-}" =~ ^PASS ] && echo "HEALTHY" || echo "UNHEALTHY")",
      "s3": "$([ "${test_results[S3 Functionality]:-}" =~ ^PASS ] && echo "HEALTHY" || echo "UNHEALTHY")",
      "cognito": "$([ "${test_results[Cognito Authentication]:-}" =~ ^PASS ] && echo "HEALTHY" || echo "UNHEALTHY")"
    },
    "recommendations": [
EOF
    
    # Add recommendations based on failures
    local recommendations=()
    
    if [[ "${test_results[CloudFormation Stacks]:-}" =~ ^FAIL ]]; then
        recommendations+=("\"Check CloudFormation stack status and resolve any deployment issues\"")
    fi
    
    if [[ "${test_results[API Endpoints]:-}" =~ ^FAIL ]]; then
        recommendations+=("\"Verify API Gateway configuration and Lambda function health\"")
    fi
    
    if [[ "${test_results[Security Configurations]:-}" =~ ^FAIL ]]; then
        recommendations+=("\"Review and improve security configurations\"")
    fi
    
    if [[ "${test_results[Monitoring and Logging]:-}" =~ ^FAIL ]]; then
        recommendations+=("\"Set up missing monitoring components and CloudWatch alarms\"")
    fi
    
    if [[ ${#recommendations[@]} -eq 0 ]]; then
        recommendations+=("\"All tests passed - deployment is healthy and ready for use\"")
    fi
    
    # Output recommendations
    local first_rec=true
    for rec in "${recommendations[@]}"; do
        if [[ "$first_rec" = true ]]; then
            first_rec=false
        else
            echo "," >> "$report_file"
        fi
        echo -n "      $rec" >> "$report_file"
    done
    
    cat >> "$report_file" << EOF

    ]
  }
}
EOF
    
    log_success "Verification report saved: $report_file"
}

# Print final summary
print_summary() {
    echo
    echo -e "${BLUE}=================================${NC}"
    echo -e "${BLUE}🧪 DEPLOYMENT VERIFICATION SUMMARY${NC}"
    echo -e "${BLUE}=================================${NC}"
    echo
    echo -e "${BLUE}Environment:${NC} $ENVIRONMENT"
    echo -e "${BLUE}Total Tests:${NC} $total_tests"
    echo -e "${GREEN}Passed:${NC} $passed_tests"
    echo -e "${RED}Failed:${NC} $failed_tests"
    echo -e "${BLUE}Success Rate:${NC} $(( passed_tests * 100 / total_tests ))%"
    echo
    
    if [[ $failed_tests -eq 0 ]]; then
        echo -e "${GREEN}🎉 ALL TESTS PASSED - DEPLOYMENT IS HEALTHY!${NC}"
        echo -e "${GREEN}Your Echoes backend is ready for use.${NC}"
    else
        echo -e "${RED}⚠️  $failed_tests TEST(S) FAILED - DEPLOYMENT HAS ISSUES${NC}"
        echo -e "${YELLOW}Review the failed tests and address the issues before proceeding.${NC}"
    fi
    
    echo
    echo -e "${BLUE}📋 Key Resources:${NC}"
    echo "  🔗 API URL: $API_GATEWAY_URL"
    echo "  👤 Cognito User Pool: $COGNITO_USER_POOL_ID"
    echo "  🗄️  S3 Bucket: $S3_BUCKET_NAME"
    echo "  📊 DynamoDB Table: $DYNAMODB_TABLE_NAME"
    
    if [[ "$GENERATE_REPORT" = true ]]; then
        echo
        echo -e "${BLUE}📄 Detailed report: ${PROJECT_ROOT}/tmp/verification-report-$ENVIRONMENT.json${NC}"
    fi
    
    echo -e "${BLUE}=================================${NC}"
}

# Main execution
main() {
    echo -e "${BLUE}🧪 Verifying deployment for: $ENVIRONMENT${NC}"
    echo "================================="
    
    load_environment_config
    
    # Run all verification tests
    test_cloudformation_stacks
    test_s3_functionality
    test_dynamodb_functionality
    test_cognito_authentication
    test_api_endpoints
    test_lambda_function
    test_monitoring
    test_security
    
    if [[ "$COMPREHENSIVE" = true ]]; then
        run_performance_tests
    fi
    
    generate_verification_report
    print_summary
    
    # Exit with appropriate code
    if [[ $failed_tests -eq 0 ]]; then
        exit 0
    else
        exit 1
    fi
}

# Run main function
main "$@"