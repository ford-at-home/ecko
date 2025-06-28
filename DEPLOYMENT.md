# Echoes Authentication System Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the complete Cognito authentication system for the Echoes audio time machine web app.

## Prerequisites

- AWS CLI configured with appropriate permissions
- Node.js 18+ installed
- AWS CDK CLI installed (`npm install -g aws-cdk`)
- Docker installed (for local development)

## Deployment Steps

### 1. Infrastructure Deployment (CDK)

```bash
# Navigate to CDK directory
cd cdk

# Install dependencies
npm install

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy all stacks
cdk deploy --all --require-approval never

# Or deploy stacks individually
cdk deploy EchoesStorageStack-dev
cdk deploy EchoesAuthStack-dev
cdk deploy EchoesApiStack-dev
```

### 2. Frontend Configuration

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Copy environment configuration
cp .env.example .env

# Update .env with actual AWS resource IDs from CDK outputs
```

### 3. Backend Configuration

```bash
# Navigate to backend directory
cd backend

# Install dependencies
npm install

# Build the application
npm run build

# Run locally for testing
npm run dev
```

## Environment Variables

### Frontend (.env)
```bash
REACT_APP_AWS_REGION=us-east-1
REACT_APP_USER_POOL_ID=<from CDK output>
REACT_APP_USER_POOL_CLIENT_ID=<from CDK output>
REACT_APP_IDENTITY_POOL_ID=<from CDK output>
REACT_APP_S3_BUCKET=<from CDK output>
REACT_APP_API_ENDPOINT=<from CDK output>
REACT_APP_STAGE=dev
```

### Backend (.env)
```bash
AWS_REGION=us-east-1
COGNITO_USER_POOL_ID=<from CDK output>
COGNITO_CLIENT_ID=<from CDK output>
S3_BUCKET_NAME=<from CDK output>
DYNAMODB_TABLE_NAME=<from CDK output>
NODE_ENV=development
```

## Testing the Authentication System

### 1. Test User Registration
```bash
# Start frontend
cd frontend && npm start

# Navigate to http://localhost:3000/auth/signup
# Create a new user account
# Check email for verification code
# Verify account at http://localhost:3000/auth/confirm
```

### 2. Test User Login
```bash
# Navigate to http://localhost:3000/auth/login
# Login with verified credentials
# Should redirect to dashboard
```

### 3. Test API Authentication
```bash
# Test protected endpoint
curl -H "Authorization: Bearer <JWT_TOKEN>" \
     https://<API_GATEWAY_URL>/dev/echoes
```

## Security Considerations

### Cognito Configuration
- User pools require email verification
- Password policy enforces complexity
- JWT tokens expire after 1 hour
- Refresh tokens valid for 30 days

### S3 Access Control
- User-scoped access: `/{userId}/*` pattern
- Presigned URLs with 1-hour expiration
- Server-side encryption enabled

### API Security
- All endpoints require valid JWT tokens
- User context extracted from token claims
- Error handling prevents information leakage

## Monitoring and Logging

### CloudWatch Logs
- Lambda function logs
- API Gateway access logs
- Cognito authentication events

### Metrics to Monitor
- Authentication success/failure rates
- Token refresh rates
- API endpoint latency
- S3 upload/download success rates

## Troubleshooting

### Common Issues

1. **CORS Errors**
   - Verify API Gateway CORS configuration
   - Check frontend origin URLs in Cognito settings

2. **Token Verification Failures**
   - Ensure correct User Pool ID and Client ID
   - Check token expiration
   - Verify JWT signature

3. **S3 Access Denied**
   - Verify IAM role permissions
   - Check object key format (`{userId}/*`)
   - Ensure presigned URL hasn't expired

4. **DynamoDB Access Issues**
   - Verify table permissions
   - Check GSI configuration
   - Monitor throttling metrics

## Cleanup

```bash
# Destroy all CDK stacks
cdk destroy --all

# Remove CDK bootstrap (optional)
# aws cloudformation delete-stack --stack-name CDKToolkit
```

## Production Considerations

### Performance Optimization
- Enable DynamoDB auto-scaling
- Configure CloudFront for S3 assets
- Implement connection pooling
- Use Redis for session caching

### Security Hardening
- Enable WAF for API Gateway
- Configure VPC endpoints
- Implement rate limiting
- Enable GuardDuty for threat detection

### High Availability
- Multi-region deployment
- DynamoDB Global Tables
- Cross-region S3 replication
- Route 53 health checks

## Support

For additional support:
1. Check CloudWatch logs for detailed error messages
2. Review AWS documentation for service-specific issues
3. Monitor AWS Health Dashboard for service outages
4. Contact AWS Support for infrastructure issues