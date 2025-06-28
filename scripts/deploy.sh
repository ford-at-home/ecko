#!/bin/bash

# Echoes CDK Deployment Script
# Usage: ./scripts/deploy.sh [environment] [profile]

set -e

ENVIRONMENT=${1:-dev}
PROFILE=${2:-default}

echo "🌀 Deploying Echoes infrastructure to environment: $ENVIRONMENT"
echo "Using AWS profile: $PROFILE"

# Check if AWS CLI is configured
if ! aws sts get-caller-identity --profile $PROFILE > /dev/null 2>&1; then
    echo "❌ AWS CLI not configured for profile: $PROFILE"
    echo "Please run: aws configure --profile $PROFILE"
    exit 1
fi

# Check if CDK is installed
if ! command -v cdk &> /dev/null; then
    echo "❌ AWS CDK not found. Please install it first:"
    echo "npm install -g aws-cdk"
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
npm install

# Install Lambda dependencies
echo "📦 Installing Lambda dependencies..."
for lambda_dir in lambda/*/; do
    if [ -f "${lambda_dir}package.json" ]; then
        echo "Installing dependencies for ${lambda_dir}"
        (cd "$lambda_dir" && npm install)
    fi
done

# Build TypeScript
echo "🔨 Building TypeScript..."
npm run build

# Bootstrap CDK (if needed)
echo "🥾 Bootstrapping CDK..."
cdk bootstrap --profile $PROFILE

# Synthesize CloudFormation templates
echo "🔧 Synthesizing CloudFormation templates..."
cdk synth --profile $PROFILE --context environment=$ENVIRONMENT

# Deploy stacks in order
echo "🚀 Deploying stacks..."

echo "Deploying Authentication Stack..."
cdk deploy Echoes-Auth-$ENVIRONMENT --profile $PROFILE --context environment=$ENVIRONMENT --require-approval never

echo "Deploying Storage Stack..."
cdk deploy Echoes-Storage-$ENVIRONMENT --profile $PROFILE --context environment=$ENVIRONMENT --require-approval never

echo "Deploying API Stack..."
cdk deploy Echoes-Api-$ENVIRONMENT --profile $PROFILE --context environment=$ENVIRONMENT --require-approval never

echo "Deploying Notification Stack..."
cdk deploy Echoes-Notif-$ENVIRONMENT --profile $PROFILE --context environment=$ENVIRONMENT --require-approval never

echo "✅ Deployment completed successfully!"
echo "📋 Stack outputs:"
cdk list --profile $PROFILE

# Display important outputs
echo "\n🔗 Important URLs and IDs:"
aws cloudformation describe-stacks --stack-name Echoes-Api-$ENVIRONMENT --profile $PROFILE --query 'Stacks[0].Outputs' --output table 2>/dev/null || echo "API stack outputs not available"
aws cloudformation describe-stacks --stack-name Echoes-Auth-$ENVIRONMENT --profile $PROFILE --query 'Stacks[0].Outputs' --output table 2>/dev/null || echo "Auth stack outputs not available"

echo "\n🎉 Echoes infrastructure is ready!"
echo "Next steps:"
echo "1. Configure your frontend with the Cognito User Pool and API Gateway endpoints"
echo "2. Set up SES for email notifications (if using email features)"
echo "3. Test the API endpoints with your application"
echo "4. Monitor CloudWatch logs and metrics"

# Save deployment info
echo "{\"environment\": \"$ENVIRONMENT\", \"profile\": \"$PROFILE\", \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" > deployment-info.json

echo "\n📝 Deployment info saved to deployment-info.json"