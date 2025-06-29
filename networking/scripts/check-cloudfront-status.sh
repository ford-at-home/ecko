#!/bin/bash

# Check CloudFront deployment status for CDK-managed distribution
PROFILE="${1:-personal}"
ENVIRONMENT="${2:-dev}"

echo "🔍 Checking CloudFront status for Echoes-$ENVIRONMENT-Network stack..."
echo ""

# Get CloudFront distribution ID from CDK stack
DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
  --stack-name "Echoes-$ENVIRONMENT-Network" \
  --profile $PROFILE \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`DistributionId`].OutputValue' \
  --output text 2>/dev/null)

if [ -z "$DISTRIBUTION_ID" ]; then
  echo "❌ No CloudFront distribution found in Echoes-$ENVIRONMENT-Network stack"
  echo "   Run 'cdk deploy Echoes-$ENVIRONMENT-Network' to create it"
  exit 1
fi

# Get distribution details
STATUS=$(aws cloudfront get-distribution --id $DISTRIBUTION_ID --profile $PROFILE --query 'Distribution.Status' --output text)
DOMAIN=$(aws cloudfront get-distribution --id $DISTRIBUTION_ID --profile $PROFILE --query 'Distribution.DomainName' --output text)

echo "Distribution ID: $DISTRIBUTION_ID"
echo "Domain: https://$DOMAIN"
echo "Status: $STATUS"
echo ""

if [ "$STATUS" = "Deployed" ]; then
  echo "✅ CloudFront is fully deployed!"
  echo "🎉 Your app is accessible at: https://$DOMAIN"
else
  echo "⏳ CloudFront is still deploying..."
  echo "This typically takes 10-20 minutes. Please check again in a few minutes."
fi