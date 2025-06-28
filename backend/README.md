# 🌀 Echoes API Backend

A FastAPI backend for the Echoes audio time machine - capturing moments as ambient sounds tied to emotion.

## 🚀 Quick Start

### Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your AWS credentials and configuration
   ```

3. **Start the server:**
   ```bash
   python start.py
   ```

4. **Access the API:**
   - API: http://localhost:8000
   - Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

### Docker Development

1. **Start with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

2. **Services available:**
   - API: http://localhost:8000
   - DynamoDB Local: http://localhost:8001
   - DynamoDB Admin: http://localhost:8002

## 📚 API Documentation

### Complete API Reference

📖 **[Comprehensive API Guide](./API_GUIDE.md)** - Detailed examples, error handling, and integration patterns

🔧 **[Postman Collection](./Echoes_API.postman_collection.json)** - Import into Postman for testing

🌐 **Interactive Docs** - Available at `/docs` in development mode

### Quick Reference

#### Core Echo Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/v1/echoes/init-upload` | Generate presigned URL for audio upload | ✅ |
| `POST` | `/api/v1/echoes?echo_id={id}` | Save echo metadata after upload | ✅ |
| `GET` | `/api/v1/echoes` | List user's echoes with filtering | ✅ |
| `GET` | `/api/v1/echoes/random` | Get random echo by emotion | ✅ |
| `GET` | `/api/v1/echoes/{echo_id}` | Get specific echo by ID | ✅ |
| `DELETE` | `/api/v1/echoes/{echo_id}` | Delete echo and audio file | ✅ |

#### System Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/` | Basic API info and status | ❌ |
| `GET` | `/health` | Detailed health check | ❌ |

### Supported Emotions

The API supports 12 distinct emotion types for categorizing audio echoes:

- `joy` - Happy, celebratory moments
- `calm` - Peaceful, serene environments  
- `sadness` - Melancholy, somber experiences
- `anger` - Intense, frustrated situations
- `fear` - Anxious, uncertain moments
- `surprise` - Unexpected, startling events
- `love` - Affectionate, tender recordings
- `nostalgia` - Reminiscent, wistful memories
- `excitement` - Energetic, thrilling experiences
- `peaceful` - Tranquil, meditative spaces
- `melancholy` - Bittersweet, contemplative moods
- `hope` - Optimistic, aspirational moments

### Audio File Support

**Supported Formats:**
- WebM (`.webm`) - Recommended for web
- WAV (`.wav`) - High quality, uncompressed
- MP3 (`.mp3`) - Compressed, widely compatible
- M4A (`.m4a`) - Apple/iTunes format
- OGG (`.ogg`) - Open source format

**Limitations:**
- Maximum file size: 10MB
- Maximum duration: 5 minutes
- Minimum duration: 0.1 seconds

### Authentication

The API uses **AWS Cognito** for user authentication:

```bash
# Include JWT token in Authorization header
curl -H "Authorization: Bearer your-jwt-token" \
  https://api.echoes.example.com/api/v1/echoes
```

**Token Requirements:**
- Valid JWT from AWS Cognito User Pool
- Token expiration: 24 hours (configurable)
- Scopes: Standard Cognito user scopes

### Error Responses

All errors follow RFC 7807 Problem Details format:

```json
{
  "error": "error_type",
  "message": "Human-readable description", 
  "details": {
    "field": "specific_field",
    "issue": "detailed_problem"
  },
  "timestamp": "2025-06-28T15:00:00Z"
}
```

**Common HTTP Status Codes:**
- `400` - Bad Request (validation errors)
- `401` - Unauthorized (authentication required)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found (resource doesn't exist)
- `413` - Payload Too Large (file size exceeded)
- `415` - Unsupported Media Type (invalid file format)
- `429` - Too Many Requests (rate limit exceeded)
- `500` - Internal Server Error (server-side issues)

### Rate Limits

**Default Limits:**
- Authenticated users: 100 requests/minute
- Unauthenticated: 20 requests/minute  
- Burst limit: +20% of base rate

**Headers:**
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1719847500
```

### Example Usage

#### Upload Audio Flow

```bash
# Step 1: Initialize upload
curl -X POST "https://api.echoes.example.com/api/v1/echoes/init-upload" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"file_extension": "webm", "content_type": "audio/webm"}'

# Step 2: Upload to S3 (use returned presigned URL)
curl -X PUT "presigned-url-from-step-1" \
  -H "Content-Type: audio/webm" \
  --data-binary @audio-file.webm

# Step 3: Create echo metadata
curl -X POST "https://api.echoes.example.com/api/v1/echoes?echo_id=echo-123" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "emotion": "joy",
    "tags": ["outdoor", "kids"],
    "transcript": "Children playing in the park",
    "file_extension": "webm",
    "duration_seconds": 30.5
  }'
```

#### List and Filter Echoes

```bash
# Get all echoes (paginated)
curl -H "Authorization: Bearer $JWT_TOKEN" \
  "https://api.echoes.example.com/api/v1/echoes?page=1&page_size=20"

# Filter by emotion
curl -H "Authorization: Bearer $JWT_TOKEN" \
  "https://api.echoes.example.com/api/v1/echoes?emotion=calm&page=1"

# Get random echo
curl -H "Authorization: Bearer $JWT_TOKEN" \
  "https://api.echoes.example.com/api/v1/echoes/random?emotion=joy"
```

## 🏗️ Architecture

### Project Structure
```
backend/
├── app/
│   ├── core/               # Configuration and utilities
│   │   ├── config.py       # Settings management
│   │   └── logging.py      # Logging configuration
│   ├── models/             # Pydantic data models
│   │   ├── echo.py         # Echo-related models
│   │   └── user.py         # User and auth models
│   ├── services/           # AWS service integrations
│   │   ├── s3_service.py   # S3 operations
│   │   ├── dynamodb_service.py  # DynamoDB operations
│   │   └── cognito_service.py   # Authentication
│   ├── routers/            # API route handlers
│   │   └── echoes.py       # Echo endpoints
│   ├── middleware/         # Custom middleware
│   │   ├── auth.py         # Authentication middleware
│   │   └── error_handler.py # Error handling
│   └── main.py             # FastAPI application
├── requirements.txt        # Python dependencies
├── Dockerfile             # Container configuration
├── docker-compose.yml     # Local development setup
└── start.py              # Development server
```

### Technology Stack

- **Framework:** FastAPI 0.104.1
- **Database:** AWS DynamoDB
- **Storage:** AWS S3
- **Authentication:** AWS Cognito + JWT
- **Runtime:** Python 3.11+
- **Container:** Docker

### AWS Services Integration

#### S3 Storage
- **Bucket Structure:** `/{userId}/{echoId}.{extension}`
- **Presigned URLs:** 1-hour expiration for uploads
- **File Validation:** Size limits and format checking

#### DynamoDB Schema
```json
{
  "userId": "partition_key",
  "echoId": "sort_key", 
  "emotion": "joy|calm|sadness|etc",
  "timestamp": "2025-06-25T15:00:00Z",
  "s3Url": "s3://bucket/path/file.webm",
  "location": {"lat": 37.5407, "lng": -77.4360},
  "tags": ["tag1", "tag2"],
  "transcript": "optional_transcription",
  "detectedMood": "ai_detected_mood"
}
```

#### Cognito Authentication
- **JWT Validation:** RS256 with JWKS verification
- **User Pool Integration:** Automatic user context
- **Development Mode:** Mock authentication when Cognito not configured

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | Enable debug mode | `true` |
| `PORT` | Server port | `8000` |
| `AWS_REGION` | AWS region | `us-east-1` |
| `S3_BUCKET_NAME` | S3 bucket for audio files | `echoes-audio-dev` |
| `DYNAMODB_TABLE_NAME` | DynamoDB table name | `EchoesTable` |
| `COGNITO_USER_POOL_ID` | Cognito User Pool ID | None |
| `JWT_SECRET_KEY` | JWT signing key | Change in production! |
| `MAX_AUDIO_FILE_SIZE` | Max upload size (bytes) | `10485760` (10MB) |
| `RATE_LIMIT_REQUESTS` | Requests per window | `100` |

### AWS Credentials

The API supports multiple AWS credential methods:
1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
2. AWS credentials file (`~/.aws/credentials`)
3. IAM roles (for EC2/ECS deployment)
4. AWS SSO

## 🧪 Development

### Running Tests
```bash
pytest tests/ -v --cov=app
```

### Code Quality
```bash
# Format code
black app/
isort app/

# Lint code  
flake8 app/
mypy app/
```

### Local DynamoDB

For development, use DynamoDB Local:
```bash
# Start DynamoDB Local
docker run -p 8001:8000 amazon/dynamodb-local

# Set environment variable
export DYNAMODB_ENDPOINT_URL=http://localhost:8001
```

## 🚢 Deployment

### Production Environment Variables
```bash
DEBUG=false
ENVIRONMENT=production
LOG_LEVEL=INFO
JWT_SECRET_KEY=your-strong-secret-key
# ... other production settings
```

### Container Deployment
```bash
# Build image
docker build -t echoes-api .

# Run container
docker run -p 8000:8000 \
  -e AWS_ACCESS_KEY_ID=your_key \
  -e AWS_SECRET_ACCESS_KEY=your_secret \
  echoes-api
```

### AWS ECS Deployment
The API is designed for AWS ECS Fargate deployment with:
- Application Load Balancer
- Auto Scaling
- CloudWatch Logs
- IAM task roles for AWS service access

## 🔒 Security

### Authentication Flow
1. Client obtains JWT from Cognito
2. Include token in `Authorization: Bearer {token}` header
3. API validates token with Cognito JWKS
4. User context extracted for request processing

### Security Headers
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 1; mode=block
- Strict-Transport-Security (production)
- Content Security Policy

### Rate Limiting
- Default: 100 requests per 60 seconds
- Per-user tracking via JWT
- IP-based for unauthenticated requests

## 📊 Monitoring

### Health Checks
- `/health` endpoint for load balancer checks
- Container health check configured
- Database connectivity validation

### Logging
- Structured JSON logs in production
- Request/response correlation IDs
- AWS service operation logging
- Error tracking with stack traces (debug mode)

### Metrics (Recommended)
- Request latency and throughput
- Error rates by endpoint
- AWS service call metrics
- Authentication success/failure rates

## 🐛 Troubleshooting

### Common Issues

**Authentication Errors:**
- Verify Cognito configuration
- Check JWT token expiration
- Validate JWKS endpoint accessibility

**AWS Service Errors:**
- Confirm AWS credentials and permissions
- Check region configuration
- Verify service endpoint URLs

**File Upload Issues:**
- Check S3 bucket permissions
- Verify presigned URL expiration
- Validate file size limits

**Database Errors:**
- Confirm DynamoDB table exists
- Check read/write capacity
- Verify item size limits

### Debug Mode
Set `DEBUG=true` for detailed error messages and request logging.

## 📄 License

Part of the Echoes Audio Time Machine project.