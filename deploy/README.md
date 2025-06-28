# Echoes Backend Deployment Automation

Complete deployment automation system for the Echoes backend infrastructure on AWS.

## 🚀 Quick Start

### One-Click Deployment

Deploy the entire backend infrastructure with a single command:

```bash
# Deploy to development environment
./deploy.sh

# Deploy to production with confirmation
./deploy.sh prod

# Deploy to staging without prompts
./deploy.sh staging --no-confirm
```

### Prerequisites

Before running the deployment, ensure you have:

1. **AWS CLI configured** with appropriate permissions
2. **AWS CDK installed** (`npm install -g aws-cdk`)
3. **Node.js 18+** and **Python 3.8+**
4. **Required permissions** for your AWS account (see [Permissions](#permissions))

## 📁 Directory Structure

```
deploy/
├── README.md                    # This file
├── scripts/                     # Individual deployment scripts
│   ├── setup-environment.sh    # Environment configuration setup
│   ├── prepare-infrastructure.sh # CDK preparation and synthesis
│   ├── deploy-storage.sh       # S3 and DynamoDB deployment
│   ├── deploy-database.sh      # Database initialization
│   ├── deploy-auth.sh          # Cognito authentication setup
│   ├── deploy-api.sh           # API Gateway and Lambda deployment
│   ├── deploy-monitoring.sh    # CloudWatch monitoring setup
│   ├── verify-deployment.sh    # Comprehensive testing
│   └── destroy.sh              # Infrastructure destruction
├── configs/                     # Environment-specific configurations
│   ├── dev/                    # Development environment config
│   ├── staging/                # Staging environment config
│   └── prod/                   # Production environment config
├── templates/                   # Generated CloudFormation templates
├── artifacts/                   # Deployment artifacts (Lambda packages, etc.)
├── utils/                      # Utility scripts and tools
└── rollback/                   # Rollback procedures and scripts
```

## 🛠️ Deployment Components

The deployment automation handles the following AWS services:

### Core Infrastructure
- **S3 Bucket** - Audio file storage with lifecycle policies
- **DynamoDB** - Echo metadata with GSI for emotion-based queries
- **Cognito** - User authentication with User Pool and Identity Pool
- **API Gateway** - RESTful API with proper CORS and throttling
- **Lambda** - FastAPI backend with optimized packaging

### Monitoring & Operations
- **CloudWatch** - Dashboards, alarms, and log aggregation
- **SNS** - Alert notifications for critical events
- **X-Ray** - Distributed tracing for performance monitoring
- **EventBridge** - Event-driven automation

### Security Features
- **IAM Roles** - Least privilege access policies
- **Encryption** - At-rest and in-transit encryption
- **CORS** - Properly configured cross-origin access
- **Public Access Blocking** - S3 security hardening

## 🔧 Individual Scripts

### Environment Setup
```bash
./deploy/scripts/setup-environment.sh -e dev
```
- Validates environment configuration
- Generates deployment-specific configs
- Sets up AWS account-specific values
- Prepares CDK context files

### Infrastructure Preparation
```bash
./deploy/scripts/prepare-infrastructure.sh -e dev
```
- Bootstraps CDK in target account/region
- Synthesizes CloudFormation templates
- Validates template syntax
- Prepares deployment artifacts

### Storage Deployment
```bash
./deploy/scripts/deploy-storage.sh -e dev
```
- Deploys S3 bucket with proper configuration
- Creates DynamoDB table with GSI
- Sets up lifecycle and backup policies
- Configures bucket notifications

### Database Initialization
```bash
./deploy/scripts/deploy-database.sh -e dev --seed
```
- Initializes DynamoDB table with required data
- Creates emotion categories configuration
- Runs database migrations
- Seeds demo data (non-prod environments)

### Authentication Setup
```bash
./deploy/scripts/deploy-auth.sh -e dev
```
- Deploys Cognito User Pool and Client
- Configures password policies and MFA
- Creates test users (non-prod)
- Sets up authentication flows

### API Deployment
```bash
./deploy/scripts/deploy-api.sh -e dev
```
- Packages and deploys Lambda function
- Creates API Gateway with proper routing
- Configures authentication and CORS
- Sets up monitoring and logging

### Monitoring Setup
```bash
./deploy/scripts/deploy-monitoring.sh -e dev
```
- Creates CloudWatch dashboards
- Sets up comprehensive alarms
- Configures SNS notifications
- Enables X-Ray tracing

### Deployment Verification
```bash
./deploy/scripts/verify-deployment.sh -e dev
```
- Tests all infrastructure components
- Validates security configurations
- Runs performance benchmarks
- Generates comprehensive report

### Infrastructure Destruction
```bash
./deploy/scripts/destroy.sh -e dev --backup
```
- Safely destroys all resources
- Creates backups before destruction
- Handles dependencies correctly
- Provides rollback information

## 🌍 Environment Management

### Supported Environments
- **dev** - Development environment with relaxed security
- **staging** - Pre-production testing environment
- **prod** - Production environment with enhanced security

### Environment Configuration

Each environment has its own configuration files:

```
environments/
├── dev/
│   └── .env.infrastructure
├── staging/
│   └── .env.infrastructure
└── prod/
    └── .env.infrastructure
```

### Environment-Specific Features

| Feature | Dev | Staging | Prod |
|---------|-----|---------|------|
| Test Users | ✅ | ✅ | ❌ |
| Debug Logging | ✅ | ✅ | ❌ |
| Point-in-Time Recovery | ❌ | ✅ | ✅ |
| Reserved Concurrency | ❌ | ✅ | ✅ |
| Enhanced Monitoring | ❌ | ✅ | ✅ |
| Backup Policies | ❌ | ✅ | ✅ |

## 🔐 Permissions

The deployment scripts require the following AWS permissions:

### Core Services
- CloudFormation (full access)
- S3 (full access)
- DynamoDB (full access)
- Lambda (full access)
- API Gateway (full access)
- Cognito (full access)

### Monitoring & Security
- CloudWatch (full access)
- SNS (full access)
- EventBridge (full access)
- X-Ray (full access)
- IAM (for role creation)

### Recommended IAM Policy
For development environments, you can use the `AdministratorAccess` policy. For production, create a custom policy with the specific permissions listed above.

## 📊 Monitoring & Alerting

### CloudWatch Dashboard
Access your environment dashboard at:
```
https://{region}.console.aws.amazon.com/cloudwatch/home?region={region}#dashboards:name=Echoes-{environment}-Dashboard
```

### Key Metrics Monitored
- API Gateway requests, errors, and latency
- Lambda invocations, errors, and duration
- DynamoDB read/write capacity and errors
- S3 storage utilization and requests

### Alert Notifications
- High error rates (>5% for 5XX, >10% for 4XX)
- High latency (>5 seconds average)
- Lambda throttling or timeouts
- DynamoDB capacity issues

## 🔄 Rollback & Recovery

### Automatic Rollback
The deployment system includes automatic rollback capabilities:
- Failed deployments trigger automatic rollback
- Stack-level rollback for CloudFormation failures
- Data backup before destructive operations

### Manual Rollback
```bash
# Rollback to previous version
./deploy/scripts/rollback.sh -e dev --to-previous

# Rollback to specific timestamp
./deploy/scripts/rollback.sh -e dev --to-timestamp 2024-01-15T10:30:00Z
```

### Data Recovery
```bash
# Restore from backup
./deploy/scripts/restore-data.sh -e dev --backup-dir /path/to/backup

# Import DynamoDB data
aws dynamodb batch-write-item --request-items file://backup/dynamodb-data.json
```

## 🧪 Testing

### Automated Testing
```bash
# Run comprehensive tests
./deploy/scripts/verify-deployment.sh -e dev --comprehensive

# Run performance tests only
./deploy/scripts/verify-deployment.sh -e dev --performance-only

# Skip tests during deployment
./deploy.sh dev --skip-tests
```

### Manual Testing
```bash
# Test API health
curl https://your-api-gateway-url/health

# Test authentication (with token)
curl -H "Authorization: Bearer $TOKEN" https://your-api-gateway-url/echoes
```

## 🚨 Troubleshooting

### Common Issues

#### CDK Bootstrap Issues
```bash
# Re-bootstrap CDK
cdk bootstrap --force

# Check bootstrap status
aws s3 ls | grep cdk-
```

#### Lambda Package Too Large
```bash
# Check package size
ls -lh deploy/artifacts/dev/lambda-deployment.zip

# Optimize dependencies
pip install --no-deps -r requirements.txt
```

#### DynamoDB Throttling
```bash
# Check table metrics
aws dynamodb describe-table --table-name EchoesTable-dev

# Increase capacity (if needed)
aws dynamodb update-table --table-name EchoesTable-dev --provisioned-throughput ReadCapacityUnits=10,WriteCapacityUnits=10
```

### Debug Mode
```bash
# Enable verbose logging
./deploy.sh dev --verbose

# Check CloudFormation events
aws cloudformation describe-stack-events --stack-name Echoes-Storage-dev
```

## 🔧 Customization

### Adding New Environments
1. Create configuration files in `config/` and `environments/`
2. Update environment validation in scripts
3. Add environment-specific settings

### Modifying Resources
1. Update CDK stack definitions in `cdk/lib/`
2. Modify deployment scripts as needed
3. Update verification tests

### Adding Monitoring
1. Add new alarms in `deploy-monitoring.sh`
2. Update dashboard configuration
3. Configure additional SNS subscriptions

## 📋 Deployment Checklist

### Pre-Deployment
- [ ] AWS CLI configured with correct profile
- [ ] Environment configuration files updated
- [ ] CDK dependencies installed
- [ ] Backend code ready for deployment

### Post-Deployment
- [ ] Run verification tests
- [ ] Check CloudWatch dashboard
- [ ] Verify API endpoints
- [ ] Set up alert subscriptions (prod)
- [ ] Document deployment details

## 🤝 Contributing

When modifying the deployment system:

1. Test changes in development environment first
2. Update documentation for any new features
3. Follow existing naming conventions
4. Add appropriate error handling
5. Include rollback procedures for new components

## 📞 Support

For deployment issues:
1. Check the verification report in `tmp/verification-report-{env}.json`
2. Review CloudWatch logs for detailed error information
3. Use the troubleshooting section above
4. Contact the development team with specific error messages

---

## 📄 License

This deployment automation is part of the Echoes project and follows the same licensing terms.