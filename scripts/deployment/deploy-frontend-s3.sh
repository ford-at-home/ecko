#!/bin/bash

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
BUCKET_NAME="echoes-frontend-dev-418272766513"
REGION="us-east-1"
AWS_PROFILE="personal"
BUILD_DIR="/Users/williamprior/Development/GitHub/ecko/frontend/dist"

echo -e "${BLUE}🚀 Echoes Frontend S3 Deployment${NC}"
echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}Bucket:${NC} $BUCKET_NAME"
echo -e "${BLUE}Region:${NC} $REGION"
echo -e "${BLUE}Build Directory:${NC} $BUILD_DIR"
echo ""

# Check if build directory exists
if [ ! -d "$BUILD_DIR" ]; then
    echo -e "${RED}❌ Build directory not found: $BUILD_DIR${NC}"
    echo "Please run 'npm run build' in the frontend directory first."
    exit 1
fi

# Check if AWS CLI is configured
echo -e "${BLUE}🔧 Checking AWS configuration...${NC}"
if ! aws --profile $AWS_PROFILE sts get-caller-identity &>/dev/null; then
    echo -e "${RED}❌ AWS CLI not configured with profile: $AWS_PROFILE${NC}"
    exit 1
fi

# Create S3 bucket if it doesn't exist
echo -e "${BLUE}🪣 Creating S3 bucket if needed...${NC}"
if aws --profile $AWS_PROFILE s3api head-bucket --bucket "$BUCKET_NAME" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Bucket already exists: $BUCKET_NAME${NC}"
else
    echo -e "${BLUE}Creating bucket: $BUCKET_NAME${NC}"
    aws --profile $AWS_PROFILE s3api create-bucket \
        --bucket "$BUCKET_NAME" \
        --region "$REGION"
    
    # Wait for bucket to be created
    aws --profile $AWS_PROFILE s3api wait bucket-exists --bucket "$BUCKET_NAME"
    echo -e "${GREEN}✅ Bucket created successfully${NC}"
fi

# Enable static website hosting
echo -e "${BLUE}🌐 Configuring static website hosting...${NC}"
aws --profile $AWS_PROFILE s3api put-bucket-website \
    --bucket "$BUCKET_NAME" \
    --website-configuration '{
        "IndexDocument": {
            "Suffix": "index.html"
        },
        "ErrorDocument": {
            "Key": "index.html"
        }
    }'

# Remove public access block FIRST (required before setting bucket policy)
echo -e "${BLUE}🔓 Removing public access block...${NC}"
aws --profile $AWS_PROFILE s3api put-public-access-block \
    --bucket "$BUCKET_NAME" \
    --public-access-block-configuration '{
        "BlockPublicAcls": false,
        "IgnorePublicAcls": false,
        "BlockPublicPolicy": false,
        "RestrictPublicBuckets": false
    }'

# Wait a moment for the change to propagate
sleep 2

# Set bucket policy for public access
echo -e "${BLUE}🔐 Setting bucket policy for public access...${NC}"
cat > /tmp/bucket-policy.json <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::$BUCKET_NAME/*"
        }
    ]
}
EOF

aws --profile $AWS_PROFILE s3api put-bucket-policy \
    --bucket "$BUCKET_NAME" \
    --policy file:///tmp/bucket-policy.json

# Deploy frontend files
echo -e "${BLUE}📤 Deploying frontend files...${NC}"
aws --profile $AWS_PROFILE s3 sync "$BUILD_DIR" "s3://$BUCKET_NAME/" \
    --delete \
    --cache-control "public,max-age=31536000,immutable" \
    --exclude "index.html"

# Upload index.html with different cache settings
aws --profile $AWS_PROFILE s3 cp "$BUILD_DIR/index.html" "s3://$BUCKET_NAME/index.html" \
    --cache-control "no-cache,no-store,must-revalidate" \
    --content-type "text/html"

# Get website URL
WEBSITE_URL="http://$BUCKET_NAME.s3-website-$REGION.amazonaws.com"

# Clean up temporary files
rm -f /tmp/bucket-policy.json

echo -e "${GREEN}"
echo "================================================================="
echo "🎉 Frontend deployment completed successfully!"
echo "================================================================="
echo -e "${NC}"
echo -e "${BLUE}Website URL:${NC} $WEBSITE_URL"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "1. Visit the website URL to test the deployment"
echo "2. Consider setting up CloudFront for HTTPS and better performance"
echo "3. Configure a custom domain if desired"
echo ""