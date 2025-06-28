#!/bin/bash

set -e

echo "🚀 Initializing LocalStack for Echoes development environment..."

# Set LocalStack endpoint
export AWS_ENDPOINT_URL="http://localstack:4566"
export AWS_ACCESS_KEY_ID="test"
export AWS_SECRET_ACCESS_KEY="test"
export AWS_DEFAULT_REGION="us-east-1"

echo "📦 Creating S3 buckets..."
awslocal s3 mb s3://echoes-audio-dev
awslocal s3 mb s3://echoes-web-dev
awslocal s3 mb s3://echoes-mobile-dev

# Set S3 bucket policies for local development
echo "🔒 Setting S3 bucket policies..."
awslocal s3api put-bucket-cors --bucket echoes-audio-dev --cors-configuration file:///opt/code/aws/s3-cors-policy.json
awslocal s3api put-bucket-policy --bucket echoes-audio-dev --policy file:///opt/code/aws/s3-bucket-policy.json

echo "🗄️ Creating DynamoDB tables..."
awslocal dynamodb create-table \
    --table-name EchoesTable-dev \
    --attribute-definitions \
        AttributeName=userId,AttributeType=S \
        AttributeName=echoId,AttributeType=S \
        AttributeName=timestamp,AttributeType=S \
        AttributeName=emotion,AttributeType=S \
    --key-schema \
        AttributeName=userId,KeyType=HASH \
        AttributeName=echoId,KeyType=RANGE \
    --global-secondary-indexes \
        IndexName=emotion-timestamp-index,KeySchema=[{AttributeName=emotion,KeyType=HASH},{AttributeName=timestamp,KeyType=RANGE}],Projection={ProjectionType=ALL},BillingMode=PAY_PER_REQUEST \
        IndexName=userId-timestamp-index,KeySchema=[{AttributeName=userId,KeyType=HASH},{AttributeName=timestamp,KeyType=RANGE}],Projection={ProjectionType=ALL},BillingMode=PAY_PER_REQUEST \
    --billing-mode PAY_PER_REQUEST

echo "👤 Creating Cognito User Pool..."
USER_POOL_ID=$(awslocal cognito-idp create-user-pool \
    --pool-name "echoes-users-dev" \
    --policies '{
        "PasswordPolicy": {
            "MinimumLength": 8,
            "RequireUppercase": true,
            "RequireLowercase": true,
            "RequireNumbers": true,
            "RequireSymbols": false
        }
    }' \
    --username-attributes email \
    --auto-verified-attributes email \
    --query 'UserPool.Id' \
    --output text)

echo "📱 Creating Cognito User Pool Client..."
CLIENT_ID=$(awslocal cognito-idp create-user-pool-client \
    --user-pool-id $USER_POOL_ID \
    --client-name "echoes-client-dev" \
    --generate-secret \
    --explicit-auth-flows ADMIN_NO_SRP_AUTH USER_PASSWORD_AUTH \
    --query 'UserPoolClient.ClientId' \
    --output text)

echo "🆔 Creating Cognito Identity Pool..."
IDENTITY_POOL_ID=$(awslocal cognito-identity create-identity-pool \
    --identity-pool-name "echoes-identity-dev" \
    --allow-unauthenticated-identities \
    --cognito-identity-providers ProviderName=cognito-idp.us-east-1.amazonaws.com/$USER_POOL_ID,ClientId=$CLIENT_ID \
    --query 'IdentityPoolId' \
    --output text)

echo "📢 Creating SNS topic..."
SNS_TOPIC_ARN=$(awslocal sns create-topic \
    --name echoes-notifications-dev \
    --query 'TopicArn' \
    --output text)

echo "📥 Creating SQS queue..."
SQS_QUEUE_URL=$(awslocal sqs create-queue \
    --queue-name echoes-queue-dev \
    --attributes '{
        "VisibilityTimeoutSeconds": "300",
        "MessageRetentionPeriod": "1209600"
    }' \
    --query 'QueueUrl' \
    --output text)

echo "📅 Creating EventBridge custom bus..."
awslocal events create-event-bus --name echoes-events-dev

echo "📊 Creating CloudWatch Log Groups..."
awslocal logs create-log-group --log-group-name /aws/lambda/echoes-dev-init-upload
awslocal logs create-log-group --log-group-name /aws/lambda/echoes-dev-save-echo
awslocal logs create-log-group --log-group-name /aws/lambda/echoes-dev-get-echoes
awslocal logs create-log-group --log-group-name /aws/lambda/echoes-dev-get-random-echo

echo "🔑 Creating test users..."
awslocal cognito-idp admin-create-user \
    --user-pool-id $USER_POOL_ID \
    --username testuser@example.com \
    --user-attributes Name=email,Value=testuser@example.com Name=email_verified,Value=true \
    --temporary-password TempPass123! \
    --message-action SUPPRESS

awslocal cognito-idp admin-set-user-password \
    --user-pool-id $USER_POOL_ID \
    --username testuser@example.com \
    --password TestPass123! \
    --permanent

echo "💾 Saving configuration to /tmp/localstack-config.json..."
cat > /tmp/localstack-config.json << EOF
{
  "userPoolId": "$USER_POOL_ID",
  "clientId": "$CLIENT_ID",
  "identityPoolId": "$IDENTITY_POOL_ID",
  "snsTopicArn": "$SNS_TOPIC_ARN",
  "sqsQueueUrl": "$SQS_QUEUE_URL",
  "region": "us-east-1",
  "endpoint": "http://localhost:4566"
}
EOF

echo "✅ LocalStack initialization complete!"
echo "📋 Configuration saved to /tmp/localstack-config.json"
echo "🌐 DynamoDB Admin UI: http://localhost:8001"
echo "📧 MailHog UI: http://localhost:8025"
echo "📊 LocalStack Health: http://localhost:4566/_localstack/health"
echo ""
echo "Test user credentials:"
echo "  Username: testuser@example.com"
echo "  Password: TestPass123!"
echo ""
echo "AWS CLI usage example:"
echo "  aws --endpoint-url=http://localhost:4566 s3 ls"