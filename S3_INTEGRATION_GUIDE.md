# S3 Integration Implementation Guide

## Overview

This document provides a comprehensive guide to the enhanced S3 integration for audio file uploads in the Echoes application. The implementation includes secure presigned URLs, user/timestamp-based file organization, comprehensive validation, and automated cleanup services.

## 🚀 Key Features

- **Secure Presigned URLs**: Generate time-limited, secure upload URLs with personal AWS profile support
- **Enhanced File Organization**: User/timestamp-based S3 key structure (`user_id/year/month/day/echo_id.extension`)
- **Comprehensive Validation**: Audio format validation, content type checking, and file size limits
- **Automated Cleanup**: Service for cleaning up orphaned files and managing storage lifecycle
- **Production-Ready Security**: CORS configuration, bucket policies, and encryption settings
- **Dual Endpoint Support**: Both `/echoes/upload-url` (new) and `/echoes/init-upload` (legacy) endpoints

## 📁 Implementation Files

### Core Services

1. **`/backend/services/s3.py`** - Enhanced S3 service with security features
2. **`/backend/services/audio_cleanup_service.py`** - Audio file lifecycle management
3. **`/backend/app/routers/echoes.py`** - Updated API endpoints (modified by service layer)
4. **`/backend/app/core/config.py`** - Enhanced configuration with timestamp support

### Configuration Files

5. **`/backend/config/s3-cors-enhanced.json`** - Production-ready CORS configuration
6. **`/backend/config/s3-bucket-policy-enhanced.json`** - Secure bucket policy template

### Deployment Scripts

7. **`/scripts/setup-s3-enhanced.sh`** - Automated S3 bucket setup and configuration
8. **`/scripts/test-s3-integration.py`** - Comprehensive integration testing suite

## 🔧 Setup Instructions

### 1. AWS Profile Configuration

Set up your personal AWS profile for secure credential management:

```bash
# Configure AWS profile
aws configure --profile your-profile-name

# Set environment variable
export AWS_PROFILE=your-profile-name
```

### 2. S3 Bucket Setup

Run the automated setup script:

```bash
# Setup for development environment
./scripts/setup-s3-enhanced.sh dev your-profile-name

# Setup for production environment
./scripts/setup-s3-enhanced.sh prod your-profile-name
```

This script will:
- Create S3 bucket with proper naming convention
- Configure encryption (AES256)
- Set up CORS policies
- Apply security policies
- Configure lifecycle rules
- Enable access logging

### 3. Environment Configuration

Update your `.env` file with the generated configuration:

```env
# S3 Configuration
S3_BUCKET_NAME=echoes-audio-dev-123456789012
AWS_REGION=us-east-1
AWS_PROFILE=your-profile-name

# S3 Settings
S3_PRESIGNED_URL_EXPIRATION=3600
MAX_AUDIO_FILE_SIZE=10485760
```

## 🎯 API Endpoints

### POST /echoes/upload-url

Generate secure presigned URL for audio upload with enhanced validation.

**Request:**
```json
{
  "file_extension": "webm",
  "content_type": "audio/webm"
}
```

**Response:**
```json
{
  "upload_url": "https://echoes-audio-dev.s3.amazonaws.com/...",
  "echo_id": "uuid-1234-5678-9abc",
  "s3_key": "user123/2025/06/28/uuid-1234.webm",
  "expires_in": 3600
}
```

**Supported Audio Formats:**
- WebM (`audio/webm`)
- WAV (`audio/wav`)
- MP3 (`audio/mpeg`)
- M4A (`audio/mp4`)
- OGG (`audio/ogg`)
- FLAC (`audio/flac`)
- AAC (`audio/aac`)

### POST /echoes/init-upload (Legacy)

Legacy endpoint that redirects to the new implementation for backward compatibility.

### Enhanced File Upload Flow

1. **Request Presigned URL**: Client calls `/echoes/upload-url`
2. **Validate Request**: Server validates file format and content type
3. **Generate Secure URL**: Server creates presigned URL with security headers
4. **Upload File**: Client uploads directly to S3 using presigned URL
5. **Create Echo**: Client calls `/echoes` to save metadata
6. **Verify Upload**: Server optionally verifies file exists in S3

## 🔐 Security Features

### Presigned URL Security

- **Time-limited URLs**: Default 1-hour expiration
- **Server-side encryption**: AES256 encryption enforced
- **Content-type validation**: Ensures uploaded files match expected types
- **File size limits**: 10MB maximum file size
- **Secure transport**: HTTPS-only uploads

### S3 Bucket Security

- **Block public access**: All public access blocked by default
- **Encryption at rest**: AES256 server-side encryption
- **Access logging**: Optional access logging to separate bucket
- **Lifecycle policies**: Automatic cleanup of old files
- **User-scoped access**: Files organized by user ID

### CORS Configuration

```json
{
  "CORSRules": [
    {
      "ID": "EchoesSecureAudioUpload",
      "AllowedHeaders": [
        "Authorization",
        "Content-Type",
        "x-amz-server-side-encryption",
        "x-amz-meta-*"
      ],
      "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
      "AllowedOrigins": [
        "http://localhost:3000",
        "https://echoes.app",
        "https://*.echoes.app"
      ],
      "ExposeHeaders": ["ETag", "x-amz-meta-*"],
      "MaxAgeSeconds": 3600
    }
  ]
}
```

## 📊 File Organization Structure

Files are organized with a user/timestamp-based hierarchy:

```
echoes-audio-bucket/
├── user123/
│   ├── 2025/
│   │   ├── 06/
│   │   │   ├── 28/
│   │   │   │   ├── echo-uuid-1.webm
│   │   │   │   ├── echo-uuid-2.mp3
│   │   │   │   └── echo-uuid-3.wav
│   │   │   └── 29/
│   │   └── 07/
│   └── 2024/
└── user456/
    └── 2025/
        └── 06/
            └── 28/
                └── echo-uuid-4.webm
```

### Benefits of This Structure

- **Efficient querying**: Easy to find files by date range
- **Lifecycle management**: Simple to apply retention policies
- **User isolation**: Clear separation of user data
- **Scalability**: Distributes files across multiple prefixes

## 🧹 Cleanup Services

### Audio Cleanup Service

The `AudioCleanupService` provides:

- **Orphaned file cleanup**: Remove S3 files without database records
- **Old file cleanup**: Remove files older than specified days
- **Storage reports**: Generate usage statistics
- **File integrity verification**: Check S3/DynamoDB consistency

### Usage Examples

```python
from backend.services.audio_cleanup_service import create_cleanup_service
from backend.services.s3 import create_s3_service

# Initialize services
s3_service = create_s3_service("echoes-audio-dev")
cleanup_service = create_cleanup_service(s3_service)

# Clean up old files (older than 1 year)
stats = await cleanup_service.cleanup_old_files("user123", older_than_days=365)

# Generate storage report
report = await cleanup_service.get_storage_report("user123")

# Verify file integrity
integrity = await cleanup_service.verify_file_integrity("user123")
```

## 🧪 Testing

### Integration Testing

Run the comprehensive test suite:

```bash
# Start your API server first
python -m uvicorn app.main:app --reload

# Run integration tests
./scripts/test-s3-integration.py http://localhost:8000 <your-jwt-token>

# Save detailed report
./scripts/test-s3-integration.py http://localhost:8000 <your-jwt-token> --save
```

### Test Coverage

The test suite covers:

- ✅ Presigned URL generation (both endpoints)
- ✅ File upload to S3
- ✅ Echo metadata creation
- ✅ Echo retrieval
- ✅ Echo deletion (with S3 cleanup)
- ✅ Validation error handling
- ✅ API health checks

### Unit Testing

```python
# Test S3 service directly
from backend.services.s3 import S3AudioService

s3_service = S3AudioService("test-bucket", "us-east-1")

# Test key generation
s3_key, echo_id = s3_service.generate_s3_key("user123", "webm")
print(f"Generated key: {s3_key}")  # user123/2025/06/28/uuid.webm

# Test validation
s3_service.validate_audio_file("webm", "audio/webm", 1024000)
```

## 🚀 Production Deployment

### Environment-Specific Configuration

#### Development
```bash
./scripts/setup-s3-enhanced.sh dev your-profile
```

#### Production
```bash
./scripts/setup-s3-enhanced.sh prod your-profile
```

### CDK Integration

The enhanced S3 service works with your existing CDK stack (`echoes-storage-stack.ts`). The CDK stack already provides:

- S3 bucket with proper configuration
- DynamoDB table for metadata
- IAM roles for user access
- CORS configuration

### Monitoring and Alerts

Consider setting up:

- **CloudWatch metrics**: Monitor upload success rates, file sizes
- **S3 event notifications**: Track file uploads and deletions
- **Cost monitoring**: Track storage costs per user
- **Error alerting**: Alert on failed uploads or cleanup operations

## 🔧 Configuration Options

### S3 Service Configuration

```python
# Create S3 service with custom settings
s3_service = S3AudioService(
    bucket_name="your-bucket",
    region="us-east-1",
    aws_profile="your-profile"  # Use personal AWS profile
)

# Override default settings
s3_service.MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
s3_service.DEFAULT_EXPIRATION = 7200  # 2 hours
```

### Application Settings

```python
# In config.py
class Settings(BaseSettings):
    # S3 Settings
    S3_BUCKET_NAME: str = "echoes-audio-dev"
    S3_PRESIGNED_URL_EXPIRATION: int = 3600
    MAX_AUDIO_FILE_SIZE: int = 10 * 1024 * 1024
    
    # Personal AWS profile support
    AWS_PROFILE: Optional[str] = None
```

## 🛠️ Troubleshooting

### Common Issues

1. **Presigned URL generation fails**
   - Check AWS credentials configuration
   - Verify S3 bucket exists and is accessible
   - Check bucket permissions

2. **File upload fails**
   - Verify CORS configuration
   - Check file size limits
   - Ensure content-type matches file extension

3. **Echo creation fails**
   - Verify S3 file was uploaded successfully
   - Check DynamoDB table configuration
   - Ensure all required fields are provided

4. **Cleanup service errors**
   - Check AWS permissions for S3 operations
   - Verify bucket and DynamoDB access
   - Monitor CloudWatch logs

### Debug Commands

```bash
# Test AWS credentials
aws sts get-caller-identity --profile your-profile

# Check bucket configuration
aws s3api get-bucket-cors --bucket your-bucket --profile your-profile

# List bucket contents
aws s3 ls s3://your-bucket/user123/ --profile your-profile

# Check bucket policy
aws s3api get-bucket-policy --bucket your-bucket --profile your-profile
```

## 📈 Performance Considerations

### Optimization Tips

1. **Use CDN**: Consider CloudFront for faster file delivery
2. **Lifecycle policies**: Automatic transition to cheaper storage classes
3. **Multipart uploads**: For large files (>5MB)
4. **Connection pooling**: Reuse HTTP connections for better performance
5. **Async operations**: Use async/await for non-blocking operations

### Monitoring Metrics

- Upload success rate
- Average upload time
- File size distribution
- Storage cost per user
- Cleanup operation efficiency

## 🔄 Migration Guide

If migrating from an existing S3 implementation:

1. **Backup existing data**: Create snapshots of current S3 bucket
2. **Run in parallel**: Deploy new service alongside existing one
3. **Gradual migration**: Move users incrementally to new structure
4. **Verify integrity**: Use cleanup service to verify file consistency
5. **Remove legacy**: Clean up old implementation after verification

## 📞 Support

For issues related to S3 integration:

1. Check the logs for detailed error messages
2. Run the integration test suite to identify issues
3. Verify AWS credentials and permissions
4. Check S3 bucket configuration and policies
5. Review CloudWatch logs for AWS service errors

## 🎉 Conclusion

This enhanced S3 integration provides a robust, secure, and scalable solution for audio file storage in the Echoes application. The implementation follows AWS best practices and includes comprehensive testing, monitoring, and cleanup capabilities.

Key benefits:
- ✅ **Security**: Secure presigned URLs with encryption
- ✅ **Organization**: User/timestamp-based file structure
- ✅ **Validation**: Comprehensive input validation
- ✅ **Cleanup**: Automated lifecycle management
- ✅ **Testing**: Complete integration test suite
- ✅ **Production-ready**: Proper configuration and monitoring

The implementation is now ready for production deployment with proper security, monitoring, and maintenance procedures in place.