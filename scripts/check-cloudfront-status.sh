#!/bin/bash

# Check CloudFront deployment status
DISTRIBUTION_ID="E25REFM8HJPLA0"
PROFILE="${1:-personal}"

echo "🔍 Checking CloudFront deployment status..."
echo ""

STATUS=$(aws cloudfront get-distribution --id $DISTRIBUTION_ID --profile $PROFILE --query 'Distribution.Status' --output text)
DOMAIN=$(aws cloudfront get-distribution --id $DISTRIBUTION_ID --profile $PROFILE --query 'Distribution.DomainName' --output text)

echo "Distribution ID: $DISTRIBUTION_ID"
echo "Domain: https://$DOMAIN"
echo "Status: $STATUS"
echo ""

if [ "$STATUS" = "Deployed" ]; then
  echo "✅ CloudFront is fully deployed!"
  echo "🎉 Your app is now accessible at: https://$DOMAIN"
  echo ""
  echo "Microphone access should now work in Chrome!"
else
  echo "⏳ CloudFront is still deploying..."
  echo "This typically takes 10-20 minutes. Please check again in a few minutes."
fi