# API Contract Documentation

## Echo Data Model

### Echo Object
```typescript
interface Echo {
  echo_id: string;
  user_id: string;
  timestamp: string; // ISO 8601
  s3_url: string;
  s3_key: string;
  emotion: EmotionType;
  tags: string[];
  transcript?: string;
  detected_mood?: string;
  location?: string;
  duration_seconds?: number;
  file_size?: number;
  created_at: string;
  updated_at: string;
}

type EmotionType = 
  | "happy"
  | "sad"
  | "angry"
  | "fearful"
  | "disgusted"
  | "surprised"
  | "nostalgic"
  | "peaceful"
  | "energetic"
  | "contemplative";
```

### Request/Response Types

#### PresignedUrlRequest
```typescript
interface PresignedUrlRequest {
  content_type: string;    // e.g., "audio/webm"
  file_size: number;       // bytes
  emotion: EmotionType;
  tags?: string[];
  location?: string;
}
```

#### PresignedUrlResponse
```typescript
interface PresignedUrlResponse {
  upload_url: string;      // S3 presigned POST URL
  fields: Record<string, string>; // Form fields for S3
  s3_key: string;         // S3 object key
  echo_id: string;        // Generated echo ID
  expires_at: string;     // ISO 8601 expiration time
}
```

#### EchoCreate
```typescript
interface EchoCreate {
  file_extension: string;
  emotion: EmotionType;
  tags?: string[];
  transcript?: string;
  detected_mood?: string;
  location?: string;
  duration_seconds?: number;
}
```

#### EchoListResponse
```typescript
interface EchoListResponse {
  echoes: EchoResponse[];
  total_count: number;
  page: number;
  page_size: number;
  has_more: boolean;
}
```

## Authentication

### JWT Token Payload
```typescript
interface TokenPayload {
  sub: string;           // User ID
  email: string;
  name?: string;
  exp: number;          // Expiration timestamp
  iat: number;          // Issued at timestamp
}
```

### User Context
```typescript
interface UserContext {
  user_id: string;
  email: string;
  name?: string;
  is_authenticated: boolean;
}
```

## Error Response Format
```typescript
interface ErrorResponse {
  detail: string;
  status_code?: number;
  error_code?: string;
  validation_errors?: Record<string, string[]>;
}
```

## S3 Upload Contract

### Direct Upload to S3
1. Frontend calls `/echoes/init-upload` to get presigned URL
2. Frontend uploads directly to S3 using multipart/form-data:
   ```
   POST https://s3.amazonaws.com/bucket
   Content-Type: multipart/form-data
   
   Form fields from presigned response
   file: <audio blob>
   ```
3. S3 returns 204 No Content on success
4. Frontend calls `/echoes` to save metadata

### File Constraints
- **Max Size**: 10MB
- **Allowed Formats**: webm, wav, mp3, m4a, ogg
- **Content Types**: audio/webm, audio/wav, audio/mpeg, audio/mp4, audio/ogg

## API Versioning

Current version: `v1`
Base path: `/api/v1`

Future versions will follow the pattern `/api/v2`, `/api/v3`, etc.