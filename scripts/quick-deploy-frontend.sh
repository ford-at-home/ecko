#!/bin/bash

# Quick frontend deployment script
set -e

echo "🚀 Quick Frontend Deployment"
echo "=========================="

# Build frontend with production config
echo "📦 Building frontend..."
cd frontend
npm run build

# Deploy to S3
echo "☁️ Deploying to S3..."
aws s3 sync dist/ s3://echoes-frontend-dev-418272766513/ \
  --profile personal \
  --delete \
  --cache-control "public,max-age=31536000,immutable" \
  --exclude "index.html"

# Upload index.html with no-cache
aws s3 cp dist/index.html s3://echoes-frontend-dev-418272766513/index.html \
  --profile personal \
  --cache-control "no-cache,no-store,must-revalidate" \
  --content-type "text/html"

# Invalidate CloudFront cache
echo "🔄 Invalidating CloudFront cache..."
aws cloudfront create-invalidation \
  --distribution-id E25REFM8HJPLA0 \
  --paths "/*" \
  --profile personal

echo "✅ Deployment complete!"
echo "🌐 Access your app at: https://d2rnrthj5zqye2.cloudfront.net"