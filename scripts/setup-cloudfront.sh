#!/bin/bash

# Setup CloudFront for HTTPS access to Echoes frontend
# This enables microphone access in Chrome

BUCKET_NAME="echoes-frontend-dev-418272766513"
PROFILE="${1:-personal}"

echo "🔒 Setting up CloudFront for HTTPS access..."

# Create CloudFront distribution
DISTRIBUTION_ID=$(aws cloudfront create-distribution \
  --profile $PROFILE \
  --output text \
  --query 'Distribution.Id' \
  --distribution-config '{
    "CallerReference": "'$(date +%s)'",
    "Comment": "Echoes Frontend HTTPS Distribution",
    "DefaultRootObject": "index.html",
    "Origins": {
      "Quantity": 1,
      "Items": [{
        "Id": "S3-'$BUCKET_NAME'",
        "DomainName": "'$BUCKET_NAME'.s3-website-us-east-1.amazonaws.com",
        "CustomOriginConfig": {
          "HTTPPort": 80,
          "HTTPSPort": 443,
          "OriginProtocolPolicy": "http-only",
          "OriginSslProtocols": {
            "Quantity": 3,
            "Items": ["TLSv1", "TLSv1.1", "TLSv1.2"]
          }
        }
      }]
    },
    "DefaultCacheBehavior": {
      "TargetOriginId": "S3-'$BUCKET_NAME'",
      "ViewerProtocolPolicy": "redirect-to-https",
      "TrustedSigners": {
        "Enabled": false,
        "Quantity": 0
      },
      "ForwardedValues": {
        "QueryString": true,
        "Cookies": {"Forward": "none"},
        "Headers": {
          "Quantity": 0
        }
      },
      "MinTTL": 0,
      "DefaultTTL": 86400,
      "MaxTTL": 31536000,
      "Compress": true,
      "AllowedMethods": {
        "Quantity": 2,
        "Items": ["HEAD", "GET"],
        "CachedMethods": {
          "Quantity": 2,
          "Items": ["HEAD", "GET"]
        }
      }
    },
    "CustomErrorResponses": {
      "Quantity": 1,
      "Items": [{
        "ErrorCode": 404,
        "ResponsePagePath": "/index.html",
        "ResponseCode": "200",
        "ErrorCachingMinTTL": 300
      }]
    },
    "Enabled": true,
    "PriceClass": "PriceClass_100"
  }')

if [ $? -eq 0 ]; then
  echo "✅ CloudFront distribution created: $DISTRIBUTION_ID"
  echo ""
  echo "⏳ Distribution is being deployed (this takes 10-20 minutes)..."
  echo ""
  
  # Get the domain name
  DOMAIN=$(aws cloudfront get-distribution \
    --id $DISTRIBUTION_ID \
    --profile $PROFILE \
    --query 'Distribution.DomainName' \
    --output text)
  
  echo "🌐 Your HTTPS URL will be: https://$DOMAIN"
  echo ""
  echo "📋 Next steps:"
  echo "1. Wait for distribution to deploy (check status with: aws cloudfront get-distribution --id $DISTRIBUTION_ID --profile $PROFILE)"
  echo "2. Access your app at: https://$DOMAIN"
  echo "3. Update your frontend environment variables with the new URL"
  echo ""
  echo "💡 To check deployment status:"
  echo "aws cloudfront get-distribution --id $DISTRIBUTION_ID --profile $PROFILE --query 'Distribution.Status' --output text"
else
  echo "❌ Failed to create CloudFront distribution"
  exit 1
fi