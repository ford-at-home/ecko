# 🔄 Migration from Manual Infrastructure to CDK

This guide helps migrate from the manually created frontend infrastructure to the CDK-managed stacks.

## Current Manual Infrastructure

### What was created manually:
1. **S3 Bucket**: `echoes-frontend-dev-418272766513` (via bash script)
2. **CloudFront Distribution**: `E25REFM8HJPLA0` (via AWS CLI)

### Problems with manual approach:
- No Infrastructure as Code
- Can't reproduce environments
- Manual configuration drift
- Inconsistent with backend (which uses CDK)
- No version control for infrastructure changes

## Migration Steps

### Option 1: Import Existing Resources (Recommended for Production)

**Step 1: Import S3 Bucket**
```bash
# Create import configuration file
cat > import-config.json << EOF
{
  "EchoesFrontendStack/WebsiteBucket": {
    "BucketName": "echoes-frontend-dev-418272766513"
  }
}
EOF

# Import the bucket
cdk import Echoes-dev-Frontend --profile personal
```

**Step 2: Import CloudFront Distribution**
```bash
# CloudFront cannot be imported directly
# You'll need to update the Network stack to use existing distribution
# Or create a new one and switch DNS
```

### Option 2: Clean Migration (Recommended for Dev)

**Step 1: Document Current Configuration**
```bash
# Save current CloudFront config
aws cloudfront get-distribution --id E25REFM8HJPLA0 --profile personal > cloudfront-backup.json

# Save S3 bucket policy
aws s3api get-bucket-policy --bucket echoes-frontend-dev-418272766513 --profile personal > bucket-policy-backup.json
```

**Step 2: Deploy CDK Stacks**
```bash
# This will create new resources with CDK management
cd cdk
cdk deploy Echoes-dev-Frontend --profile personal
cdk deploy Echoes-dev-Network --profile personal
```

**Step 3: Migrate Content**
```bash
# Sync content to new bucket
aws s3 sync s3://echoes-frontend-dev-418272766513 s3://NEW_BUCKET_NAME --profile personal
```

**Step 4: Update DNS/Links**
- Update any hardcoded URLs to new CloudFront distribution
- Update environment variables in frontend

**Step 5: Cleanup Old Resources**
```bash
# After verifying new infrastructure works
aws cloudfront delete-distribution --id E25REFM8HJPLA0 --if-match ETAG --profile personal
aws s3 rm s3://echoes-frontend-dev-418272766513 --recursive --profile personal
aws s3api delete-bucket --bucket echoes-frontend-dev-418272766513 --profile personal
```

## Post-Migration Benefits

1. **Single Deployment Command**:
   ```bash
   ./scripts/deploy.sh dev personal
   ```

2. **Consistent Infrastructure**:
   - All resources managed by CDK
   - Version controlled
   - Reproducible environments

3. **Automated Deployments**:
   - CI/CD can deploy entire stack
   - No manual steps required

4. **Better Cost Management**:
   - All resources tagged consistently
   - Easy to track costs per environment

## Rollback Plan

If migration fails:
1. Keep backup configurations
2. CDK stacks can be destroyed: `cdk destroy Echoes-dev-Frontend Echoes-dev-Network`
3. Manual resources remain untouched until explicitly deleted

## Future Deployments

After migration, all deployments will be:
```bash
# Complete infrastructure deployment
cd cdk
cdk deploy --all --profile personal --context environment=dev

# Or use the deploy script
./scripts/deploy.sh dev personal
```

No more manual S3 bucket creation or CloudFront setup scripts!