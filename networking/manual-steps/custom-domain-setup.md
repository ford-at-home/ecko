# 🌐 Custom Domain Setup Guide

This guide covers manual steps required for setting up a custom domain for the Echoes application.

## Prerequisites

- Domain registered with Route 53 or external registrar
- Access to AWS Console
- AWS CLI configured

## Manual Steps Required

### 1. Domain Registration (if not already done)

**Option A: Register with Route 53**
1. Go to Route 53 Console
2. Click "Register domain"
3. Search for your desired domain (e.g., `echoes.app`)
4. Complete registration process

**Option B: External Registrar**
1. Register domain with your preferred registrar
2. Note the nameservers for later configuration

### 2. Create Hosted Zone in Route 53

```bash
# This is automated in CDK, but if manual creation needed:
aws route53 create-hosted-zone \
  --name echoes.app \
  --caller-reference $(date +%s) \
  --profile personal
```

### 3. SSL Certificate Request (ACM)

**Manual Validation Required:**

1. Request certificate via AWS Console:
   - Navigate to ACM (Certificate Manager)
   - Click "Request a certificate"
   - Choose "Request a public certificate"
   - Add domain names:
     - `echoes.app`
     - `*.echoes.app`
   - Choose DNS validation
   - Review and request

2. **MANUAL STEP**: Add DNS validation records
   - ACM will provide CNAME records
   - Add these to your Route 53 hosted zone
   - Wait for validation (5-30 minutes)

### 4. Update CloudFront with Custom Domain

After certificate validation:

1. Go to CloudFront Console
2. Select your distribution
3. Edit General settings
4. Add Alternate Domain Names (CNAMEs):
   - `echoes.app`
   - `www.echoes.app`
5. Select your validated ACM certificate
6. Save changes

### 5. Create Route 53 Records

**MANUAL STEP**: Create alias records pointing to CloudFront

```bash
# Example - adjust with your actual values
aws route53 change-resource-record-sets \
  --hosted-zone-id Z1234567890ABC \
  --change-batch '{
    "Changes": [{
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "echoes.app",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "Z2FDTNDATAQYW2",
          "DNSName": "d2rnrthj5zqye2.cloudfront.net",
          "EvaluateTargetHealth": false
        }
      }
    }]
  }' \
  --profile personal
```

### 6. Update Nameservers (External Registrar Only)

If using external registrar:
1. Get Route 53 nameservers:
   ```bash
   aws route53 get-hosted-zone --id Z1234567890ABC --profile personal
   ```
2. Update nameservers at your registrar
3. Wait for DNS propagation (up to 48 hours)

## Verification Steps

1. Check certificate status:
   ```bash
   aws acm list-certificates --profile personal
   ```

2. Test DNS resolution:
   ```bash
   dig echoes.app
   nslookup echoes.app
   ```

3. Verify HTTPS access:
   ```bash
   curl -I https://echoes.app
   ```

## Troubleshooting

### Certificate Not Validating
- Ensure DNS records are correctly added
- Check Route 53 for CNAME records
- Wait up to 30 minutes for propagation

### Domain Not Resolving
- Verify nameservers are updated
- Check Route 53 hosted zone configuration
- Use `dig` to trace DNS resolution

### CloudFront Not Serving HTTPS
- Ensure certificate is in us-east-1 region
- Verify certificate is fully validated
- Check CloudFront alternate domain names match certificate

## Important Notes

⚠️ **Manual Steps That Cannot Be Automated:**
1. DNS validation record creation (requires domain ownership verification)
2. Nameserver updates at external registrars
3. Certificate approval in some organizations
4. Domain purchase/transfer decisions

These steps require human intervention for security and ownership verification reasons.