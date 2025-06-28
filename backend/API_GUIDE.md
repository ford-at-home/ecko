# 🌀 Echoes API Developer Guide

A comprehensive guide to integrating with the Echoes Audio Time Machine API - capturing moments as ambient sounds tied to emotion.

## Table of Contents

- [Quick Start](#quick-start)
- [Authentication](#authentication)
- [API Endpoints](#api-endpoints)
- [Request/Response Examples](#requestresponse-examples)
- [Error Handling](#error-handling)
- [Frontend Integration](#frontend-integration)
- [Rate Limits](#rate-limits)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Quick Start

### Base URL
```
Production:  https://api.echoes.example.com
Staging:     https://staging-api.echoes.example.com
Development: http://localhost:8000
```

### Basic Request
```bash
curl -X GET "https://api.echoes.example.com/health" \
  -H "Accept: application/json"
```

### Authenticated Request
```bash
curl -X GET "https://api.echoes.example.com/api/v1/echoes" \
  -H "Authorization: Bearer your-jwt-token" \
  -H "Accept: application/json"
```

## Authentication

The Echoes API uses **AWS Cognito** for authentication with JWT tokens.

### Getting a Token

1. **User Registration/Login** (via AWS Cognito)
2. **Token Retrieval** from Cognito response
3. **Include in requests** via Authorization header

### Authentication Header Format
```http
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Token Validation
- Tokens are validated against AWS Cognito JWKS
- Tokens expire after 24 hours (configurable)
- User context is extracted from token claims

### Development Mode
For development without Cognito setup, the API can run with mock authentication:
```bash
export DEBUG=true
export COGNITO_USER_POOL_ID=""
```

## API Endpoints

### System Endpoints

#### GET / - API Root
Basic API information and status.

**Request:**
```bash
curl -X GET "https://api.echoes.example.com/"
```

**Response:**
```json
{
  "message": "Echoes API is running",
  "version": "1.0.0",
  "docs": "/docs",
  "health": "/health"
}
```

#### GET /health - Health Check
Comprehensive health status including AWS service connectivity.

**Request:**
```bash
curl -X GET "https://api.echoes.example.com/health"
```

**Response:**
```json
{
  "status": "healthy",
  "service": "echoes-api",
  "version": "1.0.0",
  "environment": "production",
  "dependencies": {
    "aws_s3": "connected",
    "aws_dynamodb": "connected",
    "aws_cognito": "connected"
  },
  "timestamp": "2025-06-28T15:00:00Z"
}
```

### Echo Management Endpoints

#### POST /api/v1/echoes/init-upload - Initialize Audio Upload

Generate a presigned URL for direct S3 upload.

**Request:**
```bash
curl -X POST "https://api.echoes.example.com/api/v1/echoes/init-upload" \
  -H "Authorization: Bearer your-jwt-token" \
  -H "Content-Type: application/json" \
  -d '{
    "file_extension": "webm",
    "content_type": "audio/webm"
  }'
```

**Response:**
```json
{
  "upload_url": "https://echoes-audio.s3.amazonaws.com/user123/echo-456.webm?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...",
  "echo_id": "echo-456",
  "s3_key": "user123/echo-456.webm",
  "expires_in": 3600
}
```

**Upload to S3:**
```bash
curl -X PUT "presigned-url-from-response" \
  -H "Content-Type: audio/webm" \
  --data-binary @audio-file.webm
```

#### POST /api/v1/echoes?echo_id={id} - Create Echo

Save echo metadata after successful S3 upload.

**Request:**
```bash
curl -X POST "https://api.echoes.example.com/api/v1/echoes?echo_id=echo-456" \
  -H "Authorization: Bearer your-jwt-token" \
  -H "Content-Type: application/json" \
  -d '{
    "emotion": "joy",
    "tags": ["river", "kids", "outdoors"],
    "transcript": "Rio laughing and water splashing",
    "detected_mood": "joyful",
    "file_extension": "webm",
    "duration_seconds": 25.5,
    "location": {
      "lat": 37.5407,
      "lng": -77.4360,
      "address": "James River, Richmond, VA"
    }
  }'
```

**Response:**
```json
{
  "echo_id": "echo-456",
  "emotion": "joy",
  "timestamp": "2025-06-28T15:00:00Z",
  "s3_url": "s3://echoes-audio/user123/echo-456.webm",
  "location": {
    "lat": 37.5407,
    "lng": -77.4360,
    "address": "James River, Richmond, VA"
  },
  "tags": ["river", "kids", "outdoors"],
  "transcript": "Rio laughing and water splashing",
  "detected_mood": "joyful",
  "duration_seconds": 25.5,
  "created_at": "2025-06-28T15:00:00Z"
}
```

#### GET /api/v1/echoes - List Echoes

Get a paginated, filtered list of user's echoes.

**Request:**
```bash
curl -X GET "https://api.echoes.example.com/api/v1/echoes?emotion=joy&page=1&page_size=10" \
  -H "Authorization: Bearer your-jwt-token"
```

**Response:**
```json
{
  "echoes": [
    {
      "echo_id": "echo-456",
      "emotion": "joy",
      "timestamp": "2025-06-28T15:00:00Z",
      "s3_url": "s3://echoes-audio/user123/echo-456.webm",
      "location": {
        "lat": 37.5407,
        "lng": -77.4360,
        "address": "James River, Richmond, VA"
      },
      "tags": ["river", "kids", "outdoors"],
      "transcript": "Rio laughing and water splashing",
      "detected_mood": "joyful",
      "duration_seconds": 25.5,
      "created_at": "2025-06-28T15:00:00Z"
    }
  ],
  "total_count": 1,
  "page": 1,
  "page_size": 10,
  "has_more": false
}
```

**Query Parameters:**
- `emotion` (optional): Filter by emotion type
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Items per page (default: 20, max: 100)

**Available Emotions:**
`joy`, `calm`, `sadness`, `anger`, `fear`, `surprise`, `love`, `nostalgia`, `excitement`, `peaceful`, `melancholy`, `hope`

#### GET /api/v1/echoes/random - Get Random Echo

Get a random echo, optionally filtered by emotion.

**Request:**
```bash
curl -X GET "https://api.echoes.example.com/api/v1/echoes/random?emotion=calm" \
  -H "Authorization: Bearer your-jwt-token"
```

**Response:**
```json
{
  "echo_id": "echo-789",
  "emotion": "calm",
  "timestamp": "2025-06-27T10:30:00Z",
  "s3_url": "s3://echoes-audio/user123/echo-789.webm",
  "location": {
    "lat": 37.5407,
    "lng": -77.4360
  },
  "tags": ["meditation", "morning"],
  "transcript": "Gentle bird songs and wind through trees",
  "detected_mood": "peaceful",
  "duration_seconds": 45.2,
  "created_at": "2025-06-27T10:30:00Z"
}
```

#### GET /api/v1/echoes/{echo_id} - Get Specific Echo

Retrieve a specific echo by ID.

**Request:**
```bash
curl -X GET "https://api.echoes.example.com/api/v1/echoes/echo-456" \
  -H "Authorization: Bearer your-jwt-token"
```

**Response:**
```json
{
  "echo_id": "echo-456",
  "emotion": "joy",
  "timestamp": "2025-06-28T15:00:00Z",
  "s3_url": "s3://echoes-audio/user123/echo-456.webm",
  "location": {
    "lat": 37.5407,
    "lng": -77.4360,
    "address": "James River, Richmond, VA"
  },
  "tags": ["river", "kids", "outdoors"],
  "transcript": "Rio laughing and water splashing",
  "detected_mood": "joyful",
  "duration_seconds": 25.5,
  "created_at": "2025-06-28T15:00:00Z"
}
```

#### DELETE /api/v1/echoes/{echo_id} - Delete Echo

Delete an echo and its associated audio file.

**Request:**
```bash
curl -X DELETE "https://api.echoes.example.com/api/v1/echoes/echo-456" \
  -H "Authorization: Bearer your-jwt-token"
```

**Response:**
```
HTTP/1.1 204 No Content
```

## Error Handling

The API returns structured error responses following RFC 7807 Problem Details format.

### Error Response Format
```json
{
  "error": "error_type",
  "message": "Human-readable error message",
  "details": {
    "field": "specific_field",
    "issue": "detailed_issue_description"
  },
  "timestamp": "2025-06-28T15:00:00Z"
}
```

### Common Error Codes

#### 400 Bad Request - Validation Error
```json
{
  "error": "validation_error",
  "message": "Invalid input data",
  "details": {
    "field": "emotion",
    "issue": "must be one of: joy, calm, sadness, anger, fear, surprise, love, nostalgia, excitement, peaceful, melancholy, hope"
  },
  "timestamp": "2025-06-28T15:00:00Z"
}
```

#### 401 Unauthorized - Authentication Error
```json
{
  "error": "authentication_failed",
  "message": "Invalid or expired token",
  "details": {
    "token": "expired",
    "issued_at": "2025-06-27T15:00:00Z",
    "expired_at": "2025-06-28T15:00:00Z"
  },
  "timestamp": "2025-06-28T15:00:00Z"
}
```

#### 404 Not Found - Resource Not Found
```json
{
  "error": "resource_not_found",
  "message": "Echo not found",
  "details": {
    "echo_id": "echo-456",
    "user_id": "user123"
  },
  "timestamp": "2025-06-28T15:00:00Z"
}
```

#### 413 Payload Too Large - File Size Error
```json
{
  "error": "file_too_large",
  "message": "Audio file exceeds maximum size limit",
  "details": {
    "max_size_bytes": 10485760,
    "max_size_mb": 10,
    "received_size": 15728640
  },
  "timestamp": "2025-06-28T15:00:00Z"
}
```

#### 415 Unsupported Media Type - Invalid File Format
```json
{
  "error": "unsupported_media_type",
  "message": "Audio format not supported",
  "details": {
    "received_format": "flac",
    "supported_formats": ["webm", "wav", "mp3", "m4a", "ogg"]
  },
  "timestamp": "2025-06-28T15:00:00Z"
}
```

#### 429 Too Many Requests - Rate Limit Exceeded
```json
{
  "error": "rate_limit_exceeded",
  "message": "Rate limit exceeded. Max 100 requests per 60 seconds",
  "details": {
    "retry_after": 45,
    "limit": 100,
    "window": 60,
    "remaining": 0
  },
  "timestamp": "2025-06-28T15:00:00Z"
}
```

**Response Headers:**
```
Retry-After: 45
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1719847500
```

#### 500 Internal Server Error - Server Error
```json
{
  "error": "internal_server_error",
  "message": "An internal server error occurred",
  "details": {
    "request_id": "req-12345678",
    "service": "dynamodb",
    "operation": "create_echo"
  },
  "timestamp": "2025-06-28T15:00:00Z"
}
```

## Frontend Integration

### JavaScript/TypeScript SDK

#### Installation
```bash
npm install @echoes/api-client
# or
yarn add @echoes/api-client
```

#### Basic Setup
```typescript
import { EchoesAPIClient } from '@echoes/api-client';

const client = new EchoesAPIClient({
  baseURL: 'https://api.echoes.example.com',
  onTokenRefresh: async () => {
    // Handle token refresh logic
    return await refreshToken();
  }
});

// Set authentication token
client.setToken('your-jwt-token');
```

#### Upload Audio File
```typescript
interface UploadEchoParams {
  file: File;
  emotion: EmotionType;
  tags: string[];
  transcript?: string;
  location?: {
    lat: number;
    lng: number;
    address?: string;
  };
}

async function uploadEcho(params: UploadEchoParams) {
  try {
    // Step 1: Initialize upload
    const initResponse = await client.initUpload({
      file_extension: params.file.name.split('.').pop()!,
      content_type: params.file.type
    });

    // Step 2: Upload to S3
    await fetch(initResponse.upload_url, {
      method: 'PUT',
      body: params.file,
      headers: {
        'Content-Type': params.file.type
      }
    });

    // Step 3: Create echo metadata
    const echo = await client.createEcho(initResponse.echo_id, {
      emotion: params.emotion,
      tags: params.tags,
      transcript: params.transcript,
      file_extension: params.file.name.split('.').pop()!,
      duration_seconds: await getAudioDuration(params.file),
      location: params.location
    });

    return echo;
  } catch (error) {
    console.error('Upload failed:', error);
    throw error;
  }
}
```

#### List Echoes with Filtering
```typescript
async function getEchoes(filters: {
  emotion?: EmotionType;
  page?: number;
  pageSize?: number;
}) {
  try {
    const response = await client.listEchoes(filters);
    return response;
  } catch (error) {
    console.error('Failed to fetch echoes:', error);
    throw error;
  }
}
```

#### Error Handling
```typescript
import { EchoesAPIError } from '@echoes/api-client';

try {
  const echo = await client.getEcho('echo-123');
} catch (error) {
  if (error instanceof EchoesAPIError) {
    switch (error.code) {
      case 'authentication_failed':
        // Redirect to login
        break;
      case 'resource_not_found':
        // Show not found message
        break;
      case 'rate_limit_exceeded':
        // Show rate limit message, retry after delay
        setTimeout(() => retryRequest(), error.retryAfter * 1000);
        break;
      default:
        // Handle other errors
        console.error('API Error:', error.message);
    }
  }
}
```

### React Hooks

#### useEchoes Hook
```typescript
import { useEchoes } from '@echoes/react-hooks';

function EchoesList() {
  const {
    echoes,
    loading,
    error,
    hasMore,
    loadMore,
    refresh,
    filters,
    setFilters
  } = useEchoes({
    emotion: 'joy',
    pageSize: 20
  });

  if (loading && echoes.length === 0) {
    return <div>Loading echoes...</div>;
  }

  if (error) {
    return <div>Error: {error.message}</div>;
  }

  return (
    <div>
      {echoes.map(echo => (
        <EchoCard key={echo.echo_id} echo={echo} />
      ))}
      {hasMore && (
        <button onClick={loadMore}>Load More</button>
      )}
    </div>
  );
}
```

#### useEchoUpload Hook
```typescript
import { useEchoUpload } from '@echoes/react-hooks';

function AudioRecorder() {
  const {
    upload,
    uploading,
    progress,
    error,
    reset
  } = useEchoUpload();

  const handleUpload = async (file: File) => {
    try {
      const echo = await upload({
        file,
        emotion: 'joy',
        tags: ['recording'],
        transcript: 'User audio recording'
      });
      
      console.log('Upload successful:', echo);
    } catch (error) {
      console.error('Upload failed:', error);
    }
  };

  return (
    <div>
      <input
        type="file"
        accept="audio/*"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleUpload(file);
        }}
      />
      {uploading && (
        <div>
          Uploading: {Math.round(progress * 100)}%
        </div>
      )}
      {error && (
        <div>Error: {error.message}</div>
      )}
    </div>
  );
}
```

### Vue.js Composables

#### useEchoesAPI Composable
```typescript
import { useEchoesAPI } from '@echoes/vue-composables';

export default {
  setup() {
    const {
      echoes,
      loading,
      error,
      fetchEchoes,
      uploadEcho,
      deleteEcho
    } = useEchoesAPI();

    onMounted(() => {
      fetchEchoes({ emotion: 'calm' });
    });

    return {
      echoes,
      loading,
      error,
      fetchEchoes,
      uploadEcho,
      deleteEcho
    };
  }
};
```

## Rate Limits

### Limits by User Type

| User Type | Requests/Minute | Burst Limit |
|-----------|----------------|-------------|
| Authenticated | 100 | 120 |
| Unauthenticated | 20 | 30 |
| Premium | 200 | 250 |

### Rate Limit Headers
All responses include rate limit information:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1719847500
X-RateLimit-Window: 60
```

### Handling Rate Limits
```typescript
async function makeRequestWithRetry(request: () => Promise<any>, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await request();
    } catch (error) {
      if (error.status === 429) {
        const retryAfter = error.retryAfter || 60;
        console.log(`Rate limited, retrying after ${retryAfter}s`);
        await new Promise(resolve => setTimeout(resolve, retryAfter * 1000));
        continue;
      }
      throw error;
    }
  }
  throw new Error('Max retries exceeded');
}
```

## Best Practices

### 1. Authentication Management
- Store JWT tokens securely (httpOnly cookies recommended)
- Implement automatic token refresh
- Handle token expiration gracefully
- Never log or expose tokens in client-side code

### 2. File Upload Optimization
- Validate file format and size before upload
- Implement upload progress tracking
- Use chunked upload for large files
- Handle upload failures with retry logic

### 3. Error Handling
- Implement comprehensive error handling
- Show user-friendly error messages
- Log detailed errors for debugging
- Implement retry logic for transient errors

### 4. Performance Optimization
- Use pagination for large datasets
- Implement caching for frequently accessed data
- Optimize network requests with proper headers
- Use compression for large payloads

### 5. Security
- Validate all input data
- Use HTTPS for all API calls
- Implement CSRF protection
- Sanitize user-generated content

## Troubleshooting

### Common Issues

#### 1. Authentication Failures
**Symptom:** 401 Unauthorized responses

**Solutions:**
- Verify JWT token is not expired
- Check token format (Bearer prefix)
- Validate Cognito configuration
- Ensure user has proper permissions

#### 2. File Upload Failures
**Symptom:** Upload timeouts or S3 errors

**Solutions:**
- Check file size limits (10MB max)
- Verify supported formats
- Test presigned URL expiration
- Check S3 bucket permissions

#### 3. Rate Limit Issues
**Symptom:** 429 Too Many Requests

**Solutions:**
- Implement exponential backoff
- Reduce request frequency
- Use batch operations where possible
- Contact support for rate limit increases

#### 4. CORS Errors (Browser)
**Symptom:** Cross-origin request blocked

**Solutions:**
- Verify allowed origins configuration
- Check request headers
- Use proper preflight handling
- Test with API tools first

### Debug Tools

#### API Testing
```bash
# Test with curl
curl -v -X GET "https://api.echoes.example.com/health"

# Test with httpie
http GET https://api.echoes.example.com/health

# Test authentication
http GET https://api.echoes.example.com/api/v1/echoes \
  Authorization:"Bearer your-token"
```

#### Network Debugging
```javascript
// Browser network debugging
const originalFetch = window.fetch;
window.fetch = function(...args) {
  console.log('Fetch:', args);
  return originalFetch.apply(this, args)
    .then(response => {
      console.log('Response:', response);
      return response;
    });
};
```

### Getting Help

- **Documentation:** Available at `/docs` in development mode
- **Support:** support@echoes.example.com
- **GitHub Issues:** https://github.com/echoes/api/issues
- **Discord:** Join our developer community
- **Status Page:** https://status.echoes.example.com

---

**API Version:** 1.0.0  
**Last Updated:** June 28, 2025  
**Next Update:** Q3 2025 (v1.1.0 with advanced search and analytics)