# 🌀 Echoes CDK Infrastructure

Complete AWS CDK infrastructure for the Echoes audio time machine application.

## 📁 Project Structure

```
├── bin/
│   └── echoes-cdk.ts          # CDK app entry point
├── lib/
│   ├── echoes-storage-stack.ts # S3 + DynamoDB
│   ├── echoes-api-stack.ts     # API Gateway + Lambda
│   ├── echoes-auth-stack.ts    # Cognito authentication
│   └── echoes-notif-stack.ts   # EventBridge + SNS notifications
├── lambda/
│   ├── init-upload/            # Generate S3 presigned URLs
│   ├── save-echo/              # Save echo metadata
│   ├── get-echoes/             # Retrieve echoes with filtering
│   └── get-random-echo/        # Get weighted random echo
├── scripts/
│   ├── deploy.sh               # Deployment script
│   └── destroy.sh              # Destruction script
├── config/
│   ├── dev.json                # Development environment config
│   └── prod.json               # Production environment config
└── package.json                # Dependencies and scripts
```

## 🚀 Quick Start

### Prerequisites

1. **AWS CLI configured**:
   ```bash
   aws configure --profile dev
   aws configure --profile prod
   ```

2. **Node.js and npm installed**

3. **AWS CDK installed globally**:
   ```bash
   npm install -g aws-cdk
   ```

### Deployment

1. **Deploy to development**:
   ```bash
   ./scripts/deploy.sh dev dev-profile
   ```

2. **Deploy to production**:
   ```bash
   ./scripts/deploy.sh prod prod-profile
   ```

### Manual Commands

```bash
# Install dependencies
npm install

# Build TypeScript
npm run build

# Synthesize CloudFormation
npm run synth

# Deploy all stacks
npm run deploy:dev
npm run deploy:prod

# Destroy all stacks
npm run destroy:dev
npm run destroy:prod
```

## 🏗️ Architecture Overview

### Stack Dependencies

```
EchoesAuthStack (foundational)
    ├── EchoesStorageStack (foundational)
    │   ├── EchoesApiStack (depends on Auth + Storage)
    │   └── EchoesNotifStack (depends on Storage)
```

### EchoesStorageStack

- **S3 Bucket**: `echoes-audio-{env}`
  - Structure: `/{userId}/{echoId}.webm`
  - CORS enabled for frontend uploads
  - Lifecycle rules for cost optimization
  - Encryption at rest

- **DynamoDB Table**: `EchoesTable-{env}`
  - Partition key: `userId`
  - Sort key: `echoId`
  - GSI: `emotion-timestamp-index`
  - GSI: `userId-emotion-index`
  - Pay-per-request billing
  - Point-in-time recovery (prod only)

### EchoesAuthStack

- **Cognito User Pool**: User registration/login
- **Cognito Identity Pool**: Federated identities for S3 access
- **IAM Roles**: Scoped permissions for authenticated/unauthenticated users
- **Hosted UI**: Optional OAuth flows

### EchoesApiStack

- **API Gateway**: RESTful API with Cognito authorization
- **Lambda Functions**:
  - `init-upload`: Generate S3 presigned URLs
  - `save-echo`: Store echo metadata in DynamoDB
  - `get-echoes`: Retrieve echoes with filtering/pagination
  - `get-random-echo`: Weighted random echo selection
- **CloudWatch**: Monitoring and alerting

### EchoesNotifStack

- **SNS Topic**: Notification distribution
- **EventBridge Rules**: Scheduled reminder processing
- **Lambda Functions**:
  - Notification processor (email/push)
  - Echo reminder scheduler
  - Weekly summary generator
- **SES Integration**: Email notifications

## 📊 API Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/echoes/init-upload` | POST | Generate S3 presigned URL | ✅ |
| `/echoes` | POST | Save echo metadata | ✅ |
| `/echoes` | GET | Get echoes with filtering | ✅ |
| `/echoes/random` | GET | Get random echo | ✅ |

### Query Parameters

- **GET /echoes**:
  - `emotion`: Filter by emotion
  - `limit`: Number of results (max 100)
  - `lastEvaluatedKey`: Pagination token
  - `sortBy`: Sort field
  - `sortOrder`: asc/desc
  - `tags`: Comma-separated tags
  - `startDate`/`endDate`: Date range

- **GET /echoes/random**:
  - `emotion`: Filter by emotion
  - `excludeRecent`: Exclude recent echoes
  - `minDaysOld`: Minimum age in days
  - `tags`: Comma-separated tags

## 🔒 Security Features

### Authentication
- Cognito User Pool with customizable password policies
- Identity Pool for temporary AWS credentials
- JWT tokens with configurable expiration

### Authorization
- IAM roles with least-privilege access
- User-scoped S3 and DynamoDB permissions
- API Gateway Cognito authorizer

### Data Protection
- S3 encryption at rest (AWS managed)
- DynamoDB encryption at rest (AWS managed)
- HTTPS only for all API endpoints
- CORS restrictions (configurable per environment)

## 📈 Monitoring & Observability

### CloudWatch Alarms
- API Gateway 4xx/5xx errors
- API Gateway latency
- Lambda function errors and duration
- DynamoDB throttling
- S3 bucket size

### Logging
- API Gateway access logs
- Lambda function logs with configurable retention
- Structured logging for easy querying

### X-Ray Tracing
- Enabled for all Lambda functions
- Distributed tracing across services

## 💰 Cost Optimization

### S3
- Lifecycle rules for Infrequent Access transition
- Automatic cleanup of incomplete multipart uploads
- Optional versioning (prod only)

### DynamoDB
- Pay-per-request billing mode
- Efficient GSI design
- No unused global tables

### Lambda
- Right-sized memory allocation
- Dead letter queues for error handling
- Log retention policies

## 🌍 Environment Configuration

### Development
- Relaxed CORS policies
- Auto-delete resources on stack deletion
- Shorter log retention
- Basic monitoring

### Production
- Strict CORS policies
- Resource retention policies
- Extended log retention
- Comprehensive monitoring and alerting
- Point-in-time recovery
- Enhanced security settings

## 🔧 Customization

### Environment Variables
All Lambda functions receive:
```bash
ECHOES_TABLE_NAME=EchoesTable-{env}
AUDIOS_BUCKET_NAME=echoes-audio-{env}
USER_POOL_ID=us-east-1_XXXXXXXXX
IDENTITY_POOL_ID=us-east-1:XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
ENVIRONMENT={env}
```

### Configuration Files
- `config/dev.json`: Development settings
- `config/prod.json`: Production settings
- Override any stack properties

## 🚨 Troubleshooting

### Common Issues

1. **Deployment fails with permissions error**:
   ```bash
   # Check AWS credentials
   aws sts get-caller-identity --profile your-profile
   ```

2. **S3 bucket already exists**:
   - Bucket names must be globally unique
   - Modify the bucket name in the stack

3. **DynamoDB table not found**:
   - Ensure stacks are deployed in correct order
   - Check CloudFormation outputs

4. **CORS errors in frontend**:
   - Update CORS origins in configuration
   - Redeploy API stack

### Logs

```bash
# View API Gateway logs
aws logs describe-log-groups --log-group-name-prefix "/aws/apigateway/echoes"

# View Lambda logs
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/echoes"

# Tail Lambda logs
aws logs tail /aws/lambda/echoes-init-upload-dev --follow
```

## 🔄 CI/CD Integration

Example GitHub Actions workflow:

```yaml
name: Deploy Echoes Infrastructure

on:
  push:
    branches: [main]
    paths: ['cdk/**']

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - name: Install dependencies
        run: npm install
      - name: Deploy to dev
        run: ./scripts/deploy.sh dev
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
      - name: Deploy to prod
        if: github.ref == 'refs/heads/main'
        run: ./scripts/deploy.sh prod
```

## 📞 Support

For issues or questions:
1. Check CloudWatch logs
2. Review CloudFormation events
3. Validate IAM permissions
4. Ensure all dependencies are deployed

---

**🌀 Built with love for capturing life's precious moments**