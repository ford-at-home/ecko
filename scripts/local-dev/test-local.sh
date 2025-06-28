#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Testing Echoes Local Development Environment${NC}"
echo -e "${BLUE}===============================================${NC}"

FAILED_TESTS=0
TOTAL_TESTS=0

# Helper function to run tests
run_test() {
    local test_name="$1"
    local test_command="$2"
    local expected_result="$3"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo -e "${BLUE}🔍 Testing: $test_name${NC}"
    
    if eval "$test_command" > /dev/null 2>&1; then
        if [ -z "$expected_result" ] || eval "$expected_result"; then
            echo -e "${GREEN}✅ PASS: $test_name${NC}"
        else
            echo -e "${RED}❌ FAIL: $test_name (unexpected result)${NC}"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        echo -e "${RED}❌ FAIL: $test_name${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

# Test LocalStack availability
run_test "LocalStack Health Check" "curl -s http://localhost:4566/_localstack/health"

# Test LocalStack services
run_test "LocalStack S3 Service" "aws --endpoint-url=http://localhost:4566 s3 ls"
run_test "LocalStack DynamoDB Service" "aws --endpoint-url=http://localhost:4566 dynamodb list-tables"
run_test "LocalStack SNS Service" "aws --endpoint-url=http://localhost:4566 sns list-topics"
run_test "LocalStack SQS Service" "aws --endpoint-url=http://localhost:4566 sqs list-queues"

# Test S3 buckets exist
run_test "S3 Audio Bucket" "aws --endpoint-url=http://localhost:4566 s3api head-bucket --bucket echoes-audio-dev"
run_test "S3 Web Bucket" "aws --endpoint-url=http://localhost:4566 s3api head-bucket --bucket echoes-web-dev"
run_test "S3 Mobile Bucket" "aws --endpoint-url=http://localhost:4566 s3api head-bucket --bucket echoes-mobile-dev"

# Test DynamoDB table exists
run_test "DynamoDB Echoes Table" "aws --endpoint-url=http://localhost:4566 dynamodb describe-table --table-name EchoesTable-dev"

# Test Cognito resources
run_test "Cognito User Pool" "aws --endpoint-url=http://localhost:4566 cognito-idp list-user-pools --max-results 10"
run_test "Cognito Identity Pool" "aws --endpoint-url=http://localhost:4566 cognito-identity list-identity-pools --max-results 10"

# Test PostgreSQL
run_test "PostgreSQL Connection" "pg_isready -h localhost -p 5432 -U echoes_user"

# Test Redis
run_test "Redis Connection" "redis-cli -h localhost -p 6379 ping"

# Test DynamoDB Admin UI
run_test "DynamoDB Admin UI" "curl -s http://localhost:8001 | grep -i dynamodb"

# Test MailHog UI
run_test "MailHog UI" "curl -s http://localhost:8025"

# Test CRUD operations
echo -e "${BLUE}🔧 Testing CRUD Operations...${NC}"

# Test S3 upload
TOTAL_TESTS=$((TOTAL_TESTS + 1))
echo -e "${BLUE}🔍 Testing: S3 File Upload${NC}"
TEST_FILE="test-audio.wav"
echo "test audio content" > /tmp/$TEST_FILE

if aws --endpoint-url=http://localhost:4566 s3 cp /tmp/$TEST_FILE s3://echoes-audio-dev/test/ > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS: S3 File Upload${NC}"
else
    echo -e "${RED}❌ FAIL: S3 File Upload${NC}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Test S3 download
TOTAL_TESTS=$((TOTAL_TESTS + 1))
echo -e "${BLUE}🔍 Testing: S3 File Download${NC}"

if aws --endpoint-url=http://localhost:4566 s3 cp s3://echoes-audio-dev/test/$TEST_FILE /tmp/downloaded-$TEST_FILE > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS: S3 File Download${NC}"
else
    echo -e "${RED}❌ FAIL: S3 File Download${NC}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Test DynamoDB put item
TOTAL_TESTS=$((TOTAL_TESTS + 1))
echo -e "${BLUE}🔍 Testing: DynamoDB Put Item${NC}"

TEST_ITEM='{
    "userId": {"S": "test-user-123"},
    "echoId": {"S": "test-echo-456"},
    "emotion": {"S": "happy"},
    "timestamp": {"S": "2024-01-01T12:00:00Z"},
    "s3Url": {"S": "s3://echoes-audio-dev/test/test-audio.wav"}
}'

if aws --endpoint-url=http://localhost:4566 dynamodb put-item --table-name EchoesTable-dev --item "$TEST_ITEM" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS: DynamoDB Put Item${NC}"
else
    echo -e "${RED}❌ FAIL: DynamoDB Put Item${NC}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Test DynamoDB get item
TOTAL_TESTS=$((TOTAL_TESTS + 1))
echo -e "${BLUE}🔍 Testing: DynamoDB Get Item${NC}"

KEY='{"userId": {"S": "test-user-123"}, "echoId": {"S": "test-echo-456"}}'

if aws --endpoint-url=http://localhost:4566 dynamodb get-item --table-name EchoesTable-dev --key "$KEY" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS: DynamoDB Get Item${NC}"
else
    echo -e "${RED}❌ FAIL: DynamoDB Get Item${NC}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Test SNS publish
TOTAL_TESTS=$((TOTAL_TESTS + 1))
echo -e "${BLUE}🔍 Testing: SNS Publish Message${NC}"

TOPIC_ARN="arn:aws:sns:us-east-1:000000000000:echoes-notifications-dev"
MESSAGE='{"type": "test", "message": "Test notification"}'

if aws --endpoint-url=http://localhost:4566 sns publish --topic-arn "$TOPIC_ARN" --message "$MESSAGE" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS: SNS Publish Message${NC}"
else
    echo -e "${RED}❌ FAIL: SNS Publish Message${NC}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Test Cognito user authentication (if test user exists)
TOTAL_TESTS=$((TOTAL_TESTS + 1))
echo -e "${BLUE}🔍 Testing: Cognito User Authentication${NC}"

# Get User Pool ID
USER_POOL_ID=$(aws --endpoint-url=http://localhost:4566 cognito-idp list-user-pools --max-results 10 --query 'UserPools[?Name==`echoes-users-dev`].Id' --output text)

if [ ! -z "$USER_POOL_ID" ] && [ "$USER_POOL_ID" != "None" ]; then
    # Try to get user
    if aws --endpoint-url=http://localhost:4566 cognito-idp admin-get-user --user-pool-id "$USER_POOL_ID" --username "testuser@example.com" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PASS: Cognito User Authentication${NC}"
    else
        echo -e "${YELLOW}⚠️  SKIP: Cognito test user not found${NC}"
    fi
else
    echo -e "${RED}❌ FAIL: Cognito User Pool not found${NC}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Test SAM Local API (if running)
if [ -f tmp/sam-local/sam.pid ] && kill -0 $(cat tmp/sam-local/sam.pid) 2>/dev/null; then
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo -e "${BLUE}🔍 Testing: SAM Local API Health${NC}"
    
    if curl -s http://localhost:3001/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PASS: SAM Local API Health${NC}"
    else
        echo -e "${RED}❌ FAIL: SAM Local API Health${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo -e "${YELLOW}⚠️  SKIP: SAM Local API not running${NC}"
fi

# Clean up test files
rm -f /tmp/$TEST_FILE /tmp/downloaded-$TEST_FILE

# Test Summary
echo -e "${BLUE}"
echo "================================================================="
echo "📊 Test Results Summary"
echo "================================================================="
echo -e "${NC}"

PASSED_TESTS=$((TOTAL_TESTS - FAILED_TESTS))
PASS_RATE=$((PASSED_TESTS * 100 / TOTAL_TESTS))

echo -e "${GREEN}✅ Passed: $PASSED_TESTS/${TOTAL_TESTS} tests${NC}"
echo -e "${RED}❌ Failed: $FAILED_TESTS/${TOTAL_TESTS} tests${NC}"
echo -e "${BLUE}📈 Pass Rate: $PASS_RATE%${NC}"

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}"
    echo "🎉 All tests passed! Your local environment is ready for development."
    echo -e "${NC}"
    
    echo -e "${BLUE}Next Steps:${NC}"
    echo "1. Start your frontend: npm run dev"
    echo "2. Open your browser: http://localhost:3000"
    echo "3. Check the API docs: http://localhost:3001 (if SAM Local is running)"
    echo "4. Monitor services: docker-compose -f docker-compose.local.yml logs -f"
    
    exit 0
else
    echo -e "${RED}"
    echo "⚠️  Some tests failed. Please check the services and try again."
    echo -e "${NC}"
    
    echo -e "${BLUE}Debugging Tips:${NC}"
    echo "📋 Check service status: docker-compose -f docker-compose.local.yml ps"
    echo "📊 View logs: docker-compose -f docker-compose.local.yml logs"
    echo "🔄 Restart services: ./scripts/local-dev/stop-local.sh && ./scripts/local-dev/start-local.sh"
    echo "🧹 Clean restart: ./scripts/local-dev/stop-local.sh --clean-all && ./scripts/local-dev/start-local.sh"
    
    exit 1
fi