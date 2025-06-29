# 🚨 TODO: Connect Frontend to Backend

**Date**: June 29, 2025  
**Status**: Frontend deployed but using mock data  
**Time Needed**: 1-2 hours to complete  

## 📍 Current Situation

### What's Working ✅
- **Backend API**: Live at `https://6oit6bohh3.execute-api.us-east-1.amazonaws.com/dev/`
- **Frontend**: Live at `https://d2rnrthj5zqye2.cloudfront.net` 
- **Infrastructure**: All AWS services deployed (Cognito, S3, DynamoDB, Lambda)
- **HTTPS**: CloudFront serving with SSL (microphone access works)

### What's Broken ❌
- **Frontend uses mock data** instead of real API
- **No actual data persistence** - everything is localStorage
- **No real audio uploads** to S3
- **Authentication might not be connected** to Cognito

## 🔧 Tasks to Complete

### 1. Fix Frontend Services (30 minutes)

#### File: `/frontend/src/services/echoService.ts`
**Problem**: Currently returns mock data
```typescript
async getEchoes(emotion?: string): Promise<Echo[]> {
  // For now, return mock data until backend is ready
  return this.getMockEchoes(emotion);  // ❌ REMOVE THIS
}
```

**Fix**: Implement real API calls
```typescript
async getEchoes(emotion?: string): Promise<Echo[]> {
  const endpoint = emotion ? `/echoes?emotion=${emotion}` : '/echoes';
  return this.request<Echo[]>(endpoint);
}

async saveEcho(echoData: Omit<Echo, 'echoId' | 'timestamp'>): Promise<Echo> {
  // Get presigned URL first
  const { uploadUrl, echoId } = await this.request<{uploadUrl: string, echoId: string}>('/echoes/init-upload', {
    method: 'POST',
    body: JSON.stringify({ fileName: 'audio.webm' })
  });
  
  // Upload audio to S3
  await fetch(uploadUrl, {
    method: 'PUT',
    body: echoData.audioBlob,
    headers: { 'Content-Type': 'audio/webm' }
  });
  
  // Save metadata
  return this.request<Echo>('/echoes', {
    method: 'POST',
    body: JSON.stringify({
      ...echoData,
      echoId,
      s3Url: uploadUrl.split('?')[0]
    })
  });
}
```

#### File: `/frontend/src/services/apiService.ts`
**Check**: Ensure base URL is correct
```typescript
const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://6oit6bohh3.execute-api.us-east-1.amazonaws.com/dev';
```

#### File: `/frontend/src/contexts/AuthContext.tsx`
**Check**: Ensure it's using real Cognito auth, not mock

### 2. Update Environment Variables (5 minutes)

#### File: `/frontend/.env.production`
**Verify these are correct**:
```env
VITE_API_URL=https://6oit6bohh3.execute-api.us-east-1.amazonaws.com/dev
VITE_COGNITO_USER_POOL_ID=us-east-1_5I2DeD01Z
VITE_COGNITO_CLIENT_ID=2pg4v1bqnhaf3rlmh09vss10of
VITE_S3_BUCKET=echoes-audio-dev-418272766513
```

### 3. Deploy Frontend (5 minutes)

```bash
# Build with production config
cd frontend
npm run build

# Deploy to S3 + CloudFront
./scripts/quick-deploy-frontend.sh
```

### 4. Test Everything (30 minutes)

#### Testing Checklist
- [ ] **Sign Up**: Create new account at https://d2rnrthj5zqye2.cloudfront.net
- [ ] **Verify Email**: Check email for verification code
- [ ] **Log In**: Sign in with credentials
- [ ] **Record Audio**: 
  - [ ] Click record button
  - [ ] Allow microphone access
  - [ ] Record 10-30 seconds
  - [ ] Stop recording
- [ ] **Save Echo**:
  - [ ] Select emotion
  - [ ] Add optional caption
  - [ ] Click save
- [ ] **View Echoes**: 
  - [ ] Navigate to echo list
  - [ ] See saved echo
- [ ] **Playback**:
  - [ ] Click on echo
  - [ ] Audio plays successfully

### 5. Debug Issues (30-60 minutes)

#### Common Issues & Fixes

**CORS Errors**:
```bash
# Check API Gateway CORS configuration
aws apigateway get-rest-api --rest-api-id 6oit6bohh3 --profile personal
```

**Auth Token Issues**:
- Check browser DevTools for Authorization headers
- Verify JWT token is being sent
- Check Lambda logs for auth errors

**S3 Upload Failures**:
- Check presigned URL generation
- Verify S3 bucket CORS policy
- Check browser console for upload errors

**Monitor Backend Logs**:
```bash
# Watch Lambda logs
aws logs tail /aws/lambda/echoes-main-dev --follow --profile personal
```

## 🛠️ Useful Commands

```bash
# Check API health
curl https://6oit6bohh3.execute-api.us-east-1.amazonaws.com/dev/health

# Test API with auth (get token from browser DevTools)
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  https://6oit6bohh3.execute-api.us-east-1.amazonaws.com/dev/echoes

# Check S3 bucket
aws s3 ls s3://echoes-audio-dev-418272766513/ --profile personal

# Check DynamoDB
aws dynamodb scan --table-name EchoesTable-dev --profile personal
```

## 📁 Key File Locations

- **Frontend Services**: `/frontend/src/services/`
  - `echoService.ts` - Main service to fix
  - `apiService.ts` - Base API configuration
  - `authService.ts` - Authentication

- **Frontend Config**: `/frontend/src/config/index.ts`
- **Environment Variables**: `/frontend/.env.production`
- **Deployment Script**: `/scripts/quick-deploy-frontend.sh`

## 🚦 Definition of Done

The app is ready when:
1. ✅ User can create account and log in
2. ✅ User can record audio with microphone
3. ✅ Audio saves to S3 successfully
4. ✅ Echo metadata saves to DynamoDB
5. ✅ User can see list of their echoes
6. ✅ User can play back audio echoes
7. ✅ Emotion filtering works

## 💡 Quick Wins

If short on time, focus on:
1. Just fix `echoService.ts` to use real API
2. Deploy and test basic record/playback
3. Fix auth issues if they come up

## 🔮 Future Improvements (After MVP Works)

1. **Infrastructure**: Migrate manual resources to CDK
2. **Features**: Enable AI transcription, notifications
3. **Monitoring**: Add CloudWatch dashboards
4. **Performance**: Add caching, optimize queries
5. **Security**: Add rate limiting, WAF rules

---

**Remember**: The infrastructure is fully deployed and working. You just need to connect the frontend to use the real API instead of mock data. This is primarily a code change in the frontend services layer.