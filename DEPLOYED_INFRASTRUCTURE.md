# 🚀 Echoes - Deployed Infrastructure

## Production URLs and Resources

### 🌐 API Endpoints
- **Base URL**: `https://6oit6bohh3.execute-api.us-east-1.amazonaws.com/dev/`
- **Health Check**: `https://6oit6bohh3.execute-api.us-east-1.amazonaws.com/dev/health`

### 🔐 Authentication (AWS Cognito)
- **User Pool ID**: `us-east-1_5I2DeD01Z`
- **User Pool Client ID**: `2pg4v1bqnhaf3rlmh09vss10of`
- **Identity Pool ID**: `us-east-1:b968de7a-8d17-4c31-be88-a7b9982516ed`
- **User Pool Domain**: `echoes-dev-41827276`
- **Region**: `us-east-1`

### 💾 Storage
- **S3 Bucket**: `echoes-audio-dev-418272766513`
- **DynamoDB Table**: `EchoesTable-dev`

### ⚡ Compute
- **Lambda Function**: `echoes-api-dev`
- **Lambda ARN**: `arn:aws:lambda:us-east-1:418272766513:function:echoes-api-dev`

### 📢 Notifications
- **EventBridge Bus**: `echoes-events-dev`
- **SNS Topic**: `arn:aws:sns:us-east-1:418272766513:echoes-notifications-dev`
- **SQS Queue**: `echoes-notifications-dev`

### 🔑 IAM Roles
- **Authenticated Role**: `arn:aws:iam::418272766513:role/Echoes-dev-Auth-CognitoAuthenticatedRole5CA1BC89-G72seegBe9mw`
- **User S3 Access Role**: `arn:aws:iam::418272766513:role/Echoes-dev-Storage-UserS3AccessRole3C77CE26-ahj7JHWeJG6s`

## API Endpoints Reference

### Public Endpoints (No Auth)
- `GET /` - API information
- `GET /health` - Health check

### Protected Endpoints (Require JWT Token)
- `POST /echoes/init-upload` - Get S3 presigned URL for audio upload
- `POST /echoes` - Create echo metadata
- `GET /echoes` - List user's echoes with filtering
- `GET /echoes/random?emotion={emotion}` - Get random echo by emotion
- `GET /echoes/{echo_id}` - Get specific echo
- `DELETE /echoes/{echo_id}` - Delete echo

## Authentication Flow
1. User signs up/signs in via Cognito
2. Receives JWT tokens (ID token and Access token)
3. Includes token in API requests: `Authorization: Bearer {token}`
4. Token is validated by API Gateway Cognito Authorizer

## Environment Variables for Frontend
```env
VITE_API_URL=https://6oit6bohh3.execute-api.us-east-1.amazonaws.com/dev
VITE_AWS_REGION=us-east-1
VITE_USER_POOL_ID=us-east-1_5I2DeD01Z
VITE_USER_POOL_CLIENT_ID=2pg4v1bqnhaf3rlmh09vss10of
VITE_IDENTITY_POOL_ID=us-east-1:b968de7a-8d17-4c31-be88-a7b9982516ed
```

## AWS Account Information
- **Account ID**: `418272766513`
- **Region**: `us-east-1`
- **Environment**: `dev`