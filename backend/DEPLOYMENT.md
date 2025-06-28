# Echoes FastAPI Lambda Deployment Guide

This guide covers deploying the Echoes FastAPI backend to AWS Lambda using SAM (Serverless Application Model).

## 📋 Overview

The deployment configuration includes:
- **SAM Template**: Complete infrastructure as code with Lambda, API Gateway, DynamoDB, S3, and Cognito
- **Lambda Handler**: Optimized for cold starts with proper CORS handling
- **Environment Configuration**: Separate configs for dev, staging, and prod
- **Deployment Scripts**: Automated build, deploy, and cleanup scripts
- **Dependencies**: Optimized for Lambda package size and performance

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Frontend      │───▶│ API Gateway  │───▶│ Lambda Function │
│   (React)       │    │   (CORS)     │    │   (FastAPI)     │
└─────────────────┘    └──────────────┘    └─────────────────┘
                                                     │
                        ┌─────────────────┬─────────┼─────────┬─────────────────┐
                        │                 │         │         │                 │
                        ▼                 ▼         ▼         ▼                 ▼
                ┌─────────────┐   ┌─────────────┐   │   ┌─────────────┐   ┌─────────────┐
                │  DynamoDB   │   │     S3      │   │   │   Cognito   │   │ CloudWatch  │
                │   (Data)    │   │  (Audio)    │   │   │   (Auth)    │   │   (Logs)    │
                └─────────────┘   └─────────────┘   │   └─────────────┘   └─────────────┘
                                                    │
                                              ┌─────────────┐
                                              │   Secrets   │
                                              │  Manager    │
                                              └─────────────┘
```

## 🚀 Quick Start

### Prerequisites

1. **AWS CLI** configured with appropriate credentials
2. **SAM CLI** installed ([Installation Guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html))
3. **Docker** for building Lambda packages
4. **Python 3.11** (Lambda runtime version)

### Quick Deployment

```bash
# 1. Setup environment
cd backend
./scripts/env-setup.sh -e dev

# 2. Build the application
./scripts/build.sh

# 3. Deploy to AWS
./scripts/deploy.sh -e dev
```

## 📁 File Structure

```
backend/
├── template.yaml              # SAM template (infrastructure)
├── lambda_handler.py          # Lambda entry point (optimized)
├── requirements-lambda.txt    # Production dependencies
├── requirements-dev.txt       # Development dependencies
├── samconfig.toml.template    # SAM configuration template
├── scripts/
│   ├── build.sh              # Build script
│   ├── deploy.sh             # Deployment script
│   ├── env-setup.sh          # Environment setup
│   └── cleanup.sh            # Cleanup script
├── app/                      # FastAPI application
│   ├── main.py
│   ├── core/
│   ├── routers/
│   └── ...
└── config/                   # Environment configurations
    ├── dev.env
    ├── staging.env
    └── prod.env
```

## 🔧 Configuration

### Environment Variables

Each environment has its own configuration file:

- `config/dev.env` - Development settings
- `config/staging.env` - Staging settings  
- `config/prod.env` - Production settings

Key variables:
```bash
ENVIRONMENT=dev
DEBUG=true
LOG_LEVEL=DEBUG
CORS_ALLOW_ORIGINS=http://localhost:3000
AWS_REGION=us-east-1
DYNAMODB_TABLE_NAME=EchoesTable-dev
S3_BUCKET_NAME=echoes-audio-dev-{account-id}
```

### SAM Configuration

The `samconfig.toml` file is generated automatically by the deployment scripts, but you can customize it:

```toml
[default.deploy.parameters]
stack_name = "echoes-dev-backend"
region = "us-east-1"
parameter_overrides = "Environment=dev"
```

## 🛠️ Deployment Scripts

### Environment Setup
```bash
./scripts/env-setup.sh [OPTIONS]

Options:
  -e, --environment ENV    Environment (dev, staging, prod)
  -r, --region REGION      AWS region [default: us-east-1]
  -p, --profile PROFILE    AWS profile to use
  -c, --create             Create missing AWS resources
```

### Build Script
```bash
./scripts/build.sh [OPTIONS]

Options:
  -c, --clean              Clean build artifacts
  -v, --verbose            Verbose output
  --no-optimize            Disable optimizations
```

### Deployment Script
```bash
./scripts/deploy.sh [OPTIONS]

Options:
  -e, --environment ENV    Environment to deploy
  -r, --region REGION      AWS region
  -s, --stack-name NAME    CloudFormation stack name
  -p, --profile PROFILE    AWS profile
  -b, --build-only         Build only, don't deploy
  -g, --guided             Guided deployment
  -y, --yes                Skip confirmations
```

### Cleanup Script
```bash
./scripts/cleanup.sh [OPTIONS]

Options:
  -e, --environment ENV    Environment to clean up
  -l, --local-only         Clean only local artifacts
  -f, --force              Skip confirmations
  -d, --dry-run            Show what would be deleted
```

## 🌍 Multi-Environment Deployment

### Development
```bash
./scripts/env-setup.sh -e dev
./scripts/deploy.sh -e dev
```

### Staging
```bash
./scripts/env-setup.sh -e staging
./scripts/deploy.sh -e staging
```

### Production
```bash
./scripts/env-setup.sh -e prod
./scripts/deploy.sh -e prod -p production-profile
```

## 🔒 Security Considerations

### Production Security
- JWT secrets stored in AWS Secrets Manager
- S3 buckets with encryption and versioning
- DynamoDB with encryption at rest
- CloudWatch logs with retention policies
- Strict CORS policies
- Rate limiting enabled

### IAM Permissions
The Lambda function requires these permissions:
- DynamoDB: Read/Write access to tables
- S3: Read/Write access to audio bucket
- Cognito: User management operations
- Secrets Manager: Read JWT secrets
- CloudWatch: Logging

## 📊 Monitoring & Logging

### CloudWatch Integration
- Lambda function logs: `/aws/lambda/echoes-{env}-api`
- API Gateway access logs
- Custom metrics for performance monitoring
- Error rate and latency alarms (production)

### X-Ray Tracing
Enabled for performance analysis:
```yaml
Tracing: Active  # In SAM template
```

## 🚀 Performance Optimization

### Cold Start Optimization
- Lazy loading of FastAPI app and dependencies
- Global variable reuse across invocations
- Optimized package size (~80MB)
- Higher memory allocation (1024MB) for faster execution

### Package Size Optimization
- Removed development dependencies
- Eliminated unnecessary files during build
- Used PyJWT instead of python-jose for smaller footprint
- Pinned dependency versions for consistency

## 🐛 Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Check Python path configuration
   PYTHONPATH=/var/task:/var/runtime python3 -c "from app.main import app"
   ```

2. **CORS Issues**
   ```bash
   # Verify CORS_ALLOW_ORIGINS in environment config
   # Check API Gateway CORS configuration
   ```

3. **Permission Errors**
   ```bash
   # Test AWS credentials
   aws sts get-caller-identity
   
   # Check IAM permissions
   aws iam simulate-principal-policy --policy-source-arn {role-arn} --action-names lambda:InvokeFunction
   ```

4. **Build Failures**
   ```bash
   # Clean build and retry
   ./scripts/build.sh -c -v
   ```

### Debug Mode
Enable debug logging:
```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
./scripts/deploy.sh -e dev
```

## 📝 API Endpoints

After deployment, your API will be available at:
```
https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/
```

Key endpoints:
- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /docs` - API documentation (dev only)
- `POST /api/v1/echoes` - Create echo
- `GET /api/v1/echoes` - List echoes

## 🔄 CI/CD Integration

### GitHub Actions Example
```yaml
name: Deploy to AWS
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Setup SAM
        uses: aws-actions/setup-sam@v1
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      - name: Deploy
        run: |
          cd backend
          ./scripts/env-setup.sh -e prod
          ./scripts/deploy.sh -e prod -y
```

## 📞 Support

For deployment issues:
1. Check CloudFormation stack events in AWS Console
2. Review CloudWatch logs for Lambda function
3. Validate SAM template: `sam validate`
4. Test locally: `sam local start-api`

## 🔗 Related Documentation

- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Mangum Documentation](https://mangum.io/)
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)