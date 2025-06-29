# 🌐 Echoes Networking Configuration

This directory contains networking configuration and documentation for the Echoes application, including CloudFront CDN setup, custom domains, and SSL certificates.

## 📁 Directory Structure

- `manual-steps/` - Documentation for manual configuration steps
- `scripts/` - Automation scripts for networking tasks
- `docs/` - Additional networking documentation

## 🚀 Quick Start

### Automated Deployment
The CloudFront distribution is now automatically created as part of the CDK deployment:
```bash
# Build frontend first
cd frontend
npm run build

# Deploy all infrastructure including CloudFront
cd ../cdk
cdk deploy --all --profile personal --context environment=dev

# Or deploy just the network stack
cdk deploy Echoes-dev-Network --profile personal
```

### Manual Steps Required
Some configurations require manual intervention:
1. Custom domain setup (Route 53)
2. SSL certificate validation (ACM)
3. DNS record updates

See `manual-steps/` directory for detailed guides.

## 🔗 Current Infrastructure

### Existing Manual Infrastructure (To Be Migrated)
- **CloudFront Distribution ID**: E25REFM8HJPLA0
- **CloudFront URL**: https://d2rnrthj5zqye2.cloudfront.net
- **S3 Origin**: echoes-frontend-dev-418272766513.s3-website-us-east-1.amazonaws.com
- **Status**: Created manually, not managed by CDK

### CDK-Managed Infrastructure (After Migration)
- Will be created when you run `cdk deploy Echoes-dev-Frontend Echoes-dev-Network`
- See `manual-steps/MIGRATION_FROM_MANUAL.md` for migration instructions

## 📊 Status Checking

Check CloudFront deployment status:
```bash
./scripts/check-cloudfront-status.sh
```

## 🛠️ Common Tasks

### Update CloudFront Distribution
```bash
./scripts/update-cloudfront.sh
```

### Invalidate CloudFront Cache
```bash
./scripts/invalidate-cache.sh
```

### Setup Custom Domain
See `manual-steps/custom-domain-setup.md`