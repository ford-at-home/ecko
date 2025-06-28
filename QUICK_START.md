# 🚀 Echoes Quick Start Guide

## Current Status
✅ **Backend Deployed**: API is live at https://6oit6bohh3.execute-api.us-east-1.amazonaws.com/dev/  
✅ **Database Ready**: DynamoDB table `EchoesTable-dev` is configured  
✅ **Authentication Ready**: Cognito User Pool `us-east-1_5I2DeD01Z` is set up  
✅ **Storage Ready**: S3 bucket `echoes-audio-dev-418272766513` is available  
⏳ **Frontend**: Ready to deploy  

## Test the API
```bash
# Public endpoint - should return API info
curl https://6oit6bohh3.execute-api.us-east-1.amazonaws.com/dev/health

# Protected endpoint - should return 403 (expected without auth)
curl https://6oit6bohh3.execute-api.us-east-1.amazonaws.com/dev/echoes
```

## Frontend Local Testing
```bash
cd frontend

# Copy environment variables
cp .env.example .env

# Install dependencies
npm install

# Start development server
npm run dev

# Open http://localhost:5173
```

## Frontend Deployment (S3)
```bash
cd frontend

# Build for production
npm run build

# Deploy to S3 (using swarm or manually)
aws s3 sync dist/ s3://echoes-frontend-dev-418272766513 --delete --profile personal
```

## Key Resources
- **API Docs**: See [DEPLOYED_INFRASTRUCTURE.md](./DEPLOYED_INFRASTRUCTURE.md)
- **Frontend Deploy Guide**: See [FRONTEND_DEPLOYMENT.md](./FRONTEND_DEPLOYMENT.md)
- **AWS Account**: 418272766513
- **Region**: us-east-1
- **Profile**: personal

## Architecture Overview
```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   React     │────▶│ API Gateway  │────▶│   Lambda    │
│  Frontend   │     │   + Auth     │     │  (FastAPI)  │
└─────────────┘     └──────────────┘     └─────────────┘
                             │                    │
                             ▼                    ▼
                    ┌──────────────┐     ┌─────────────┐
                    │   Cognito    │     │  DynamoDB   │
                    │ User Pool    │     │     +       │
                    └──────────────┘     │     S3      │
                                        └─────────────┘
```

## Next Steps
1. Deploy frontend using swarm orchestration
2. Create CloudFront distribution for global CDN
3. Configure custom domain (optional)
4. Set up monitoring and alerts