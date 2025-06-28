#!/bin/bash

# Echoes CDK Destroy Script
# Usage: ./scripts/destroy.sh [environment] [profile]

set -e

ENVIRONMENT=${1:-dev}
PROFILE=${2:-default}

echo "🗑️ Destroying Echoes infrastructure for environment: $ENVIRONMENT"
echo "Using AWS profile: $PROFILE"

# Confirmation prompt
read -p "Are you sure you want to destroy the $ENVIRONMENT environment? This action cannot be undone. (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Destruction cancelled."
    exit 0
fi

# Additional confirmation for production
if [ "$ENVIRONMENT" = "prod" ] || [ "$ENVIRONMENT" = "production" ]; then
    echo "⚠️  WARNING: You are about to destroy the PRODUCTION environment!"
    read -p "Type 'DESTROY-PRODUCTION' to confirm: " prod_confirm
    if [ "$prod_confirm" != "DESTROY-PRODUCTION" ]; then
        echo "Production destruction cancelled."
        exit 0
    fi
fi

# Check if AWS CLI is configured
if ! aws sts get-caller-identity --profile $PROFILE > /dev/null 2>&1; then
    echo "❌ AWS CLI not configured for profile: $PROFILE"
    exit 1
fi

# Build TypeScript (needed for CDK to understand the stacks)
echo "🔨 Building TypeScript..."
npm run build

# Destroy stacks in reverse order (dependencies)
echo "🗑️ Destroying stacks in reverse order..."

echo "Destroying Notification Stack..."
cdk destroy Echoes-Notif-$ENVIRONMENT --profile $PROFILE --context environment=$ENVIRONMENT --force

echo "Destroying API Stack..."
cdk destroy Echoes-Api-$ENVIRONMENT --profile $PROFILE --context environment=$ENVIRONMENT --force

# Note: Storage stack might fail if S3 bucket has objects
echo "Destroying Storage Stack..."
echo "⚠️  Note: If S3 bucket is not empty, you may need to empty it manually first"
cdk destroy Echoes-Storage-$ENVIRONMENT --profile $PROFILE --context environment=$ENVIRONMENT --force

echo "Destroying Authentication Stack..."
cdk destroy Echoes-Auth-$ENVIRONMENT --profile $PROFILE --context environment=$ENVIRONMENT --force

echo "✅ Destruction completed!"

# Clean up deployment info
if [ -f "deployment-info.json" ]; then
    rm deployment-info.json
    echo "Cleaned up deployment-info.json"
fi

echo "🎉 All Echoes infrastructure has been destroyed for environment: $ENVIRONMENT"
echo "\nNote: Some resources might take a few minutes to fully delete."
echo "CloudWatch logs are retained according to the retention policy set in the stacks."