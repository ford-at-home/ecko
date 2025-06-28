# 🎨 Frontend Deployment Guide

## Prerequisites
- AWS CLI configured with the `personal` profile
- Node.js 18+ installed
- Access to the AWS account (418272766513)

## Deployment Options

### Option 1: S3 + CloudFront (Recommended)
This deploys the frontend as a static website with global CDN distribution.

#### Step 1: Create S3 Bucket for Frontend
```bash
# Create bucket
aws s3 mb s3://echoes-frontend-dev-418272766513 --region us-east-1 --profile personal

# Enable static website hosting
aws s3 website s3://echoes-frontend-dev-418272766513 \
  --index-document index.html \
  --error-document index.html \
  --profile personal
```

#### Step 2: Create Bucket Policy
```bash
cat > frontend-bucket-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::echoes-frontend-dev-418272766513/*"
    }
  ]
}
EOF

aws s3api put-bucket-policy \
  --bucket echoes-frontend-dev-418272766513 \
  --policy file://frontend-bucket-policy.json \
  --profile personal
```

#### Step 3: Configure Frontend Environment
```bash
cd frontend
cat > .env.production << EOF
VITE_API_URL=https://6oit6bohh3.execute-api.us-east-1.amazonaws.com/dev
VITE_AWS_REGION=us-east-1
VITE_USER_POOL_ID=us-east-1_5I2DeD01Z
VITE_USER_POOL_CLIENT_ID=2pg4v1bqnhaf3rlmh09vss10of
VITE_IDENTITY_POOL_ID=us-east-1:b968de7a-8d17-4c31-be88-a7b9982516ed
EOF
```

#### Step 4: Build and Deploy
```bash
# Install dependencies
npm install

# Build for production
npm run build

# Deploy to S3
aws s3 sync dist/ s3://echoes-frontend-dev-418272766513 \
  --delete \
  --profile personal

# Set cache headers for better performance
aws s3 cp s3://echoes-frontend-dev-418272766513 s3://echoes-frontend-dev-418272766513 \
  --recursive \
  --metadata-directive REPLACE \
  --cache-control "public, max-age=3600" \
  --exclude "*.html" \
  --profile personal

aws s3 cp s3://echoes-frontend-dev-418272766513 s3://echoes-frontend-dev-418272766513 \
  --recursive \
  --metadata-directive REPLACE \
  --cache-control "no-cache" \
  --exclude "*" \
  --include "*.html" \
  --profile personal
```

#### Step 5: Create CloudFront Distribution (Optional but Recommended)
```bash
aws cloudfront create-distribution \
  --origin-domain-name echoes-frontend-dev-418272766513.s3-website-us-east-1.amazonaws.com \
  --default-root-object index.html \
  --profile personal
```

### Option 2: AWS Amplify (Simplest)
AWS Amplify provides CI/CD, hosting, and automatic deployments from Git.

```bash
# Install Amplify CLI
npm install -g @aws-amplify/cli

# Initialize Amplify in the frontend directory
cd frontend
amplify init

# Add hosting
amplify add hosting

# Deploy
amplify publish
```

### Option 3: Local Testing
For development and testing:

```bash
cd frontend
npm install
npm run dev
```

Access at `http://localhost:5173`

## Post-Deployment

### Access URLs
- **S3 Website**: `http://echoes-frontend-dev-418272766513.s3-website-us-east-1.amazonaws.com`
- **CloudFront**: `https://[distribution-id].cloudfront.net`
- **Custom Domain**: Can be configured in Route 53

### Testing the Deployment
1. Visit the frontend URL
2. Click "Sign Up" to create a new account
3. Verify your email
4. Sign in with your credentials
5. Try recording an audio echo
6. Test emotion filtering and playback

### Troubleshooting

#### CORS Issues
If you see CORS errors, ensure the API Gateway has proper CORS headers configured.

#### Authentication Issues
- Check browser console for errors
- Verify Cognito configuration in `.env.production`
- Ensure the API URL is correct

#### Upload Issues
- Check S3 bucket permissions
- Verify presigned URL generation
- Check browser console for errors

## Environment Variables Reference

| Variable | Description | Value |
|----------|-------------|-------|
| `VITE_API_URL` | API Gateway endpoint | `https://6oit6bohh3.execute-api.us-east-1.amazonaws.com/dev` |
| `VITE_AWS_REGION` | AWS region | `us-east-1` |
| `VITE_USER_POOL_ID` | Cognito User Pool ID | `us-east-1_5I2DeD01Z` |
| `VITE_USER_POOL_CLIENT_ID` | Cognito App Client ID | `2pg4v1bqnhaf3rlmh09vss10of` |
| `VITE_IDENTITY_POOL_ID` | Cognito Identity Pool ID | `us-east-1:b968de7a-8d17-4c31-be88-a7b9982516ed` |

## Security Considerations
- Never commit `.env` files with real credentials
- Use environment-specific configurations
- Enable CloudFront security headers
- Configure proper S3 bucket policies
- Use HTTPS for all communications