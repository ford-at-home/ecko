#!/usr/bin/env python3

"""
S3 Service Usage Examples
Demonstrates how to use the enhanced S3 audio service
"""

import asyncio
import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.s3 import create_s3_service
from backend.services.audio_cleanup_service import create_cleanup_service


async def example_presigned_url_generation():
    """Example: Generate presigned URLs for audio uploads"""
    print("🔗 Presigned URL Generation Example")
    print("=" * 50)
    
    # Initialize S3 service
    s3_service = create_s3_service(
        bucket_name="echoes-audio-dev",
        region="us-east-1",
        aws_profile=os.getenv("AWS_PROFILE", "default")
    )
    
    try:
        # Generate presigned URL for WebM upload
        upload_data = s3_service.generate_presigned_upload_url(
            user_id="user123",
            file_extension="webm",
            content_type="audio/webm",
            file_size=2048000  # 2MB
        )
        
        print(f"✅ Generated presigned URL successfully!")
        print(f"   Echo ID: {upload_data['echo_id']}")
        print(f"   S3 Key: {upload_data['s3_key']}")
        print(f"   Expires in: {upload_data['expires_in']} seconds")
        print(f"   Max file size: {upload_data['max_file_size']} bytes")
        print(f"   Upload URL: {upload_data['upload_url'][:50]}...")
        
        return upload_data
        
    except Exception as e:
        print(f"❌ Error generating presigned URL: {e}")
        return None


async def example_file_operations():
    """Example: File operations (check, metadata, delete)"""
    print("\n📁 File Operations Example")
    print("=" * 50)
    
    s3_service = create_s3_service(
        bucket_name="echoes-audio-dev",
        region="us-east-1",
        aws_profile=os.getenv("AWS_PROFILE", "default")
    )
    
    # Example S3 key (this would come from a real upload)
    test_s3_key = "user123/2025/06/28/example-echo-id.webm"
    
    try:
        # Check if file exists
        exists = s3_service.check_file_exists(test_s3_key)
        print(f"File exists: {exists}")
        
        if exists:
            # Get file metadata
            metadata = s3_service.get_file_metadata(test_s3_key)
            if metadata:
                print(f"File size: {metadata['size']} bytes")
                print(f"Content type: {metadata['content_type']}")
                print(f"Last modified: {metadata['last_modified']}")
                print(f"ETag: {metadata['etag']}")
        
        # Generate download URL
        download_url = s3_service.generate_presigned_download_url(
            test_s3_key,
            expires_in=1800  # 30 minutes
        )
        print(f"Download URL: {download_url[:50]}...")
        
    except Exception as e:
        print(f"❌ Error with file operations: {e}")


async def example_storage_statistics():
    """Example: Get storage statistics for a user"""
    print("\n📊 Storage Statistics Example")
    print("=" * 50)
    
    s3_service = create_s3_service(
        bucket_name="echoes-audio-dev",
        region="us-east-1",
        aws_profile=os.getenv("AWS_PROFILE", "default")
    )
    
    try:
        stats = s3_service.get_user_storage_stats("user123")
        
        print(f"User ID: {stats['user_id']}")
        print(f"Total files: {stats['total_files']}")
        print(f"Total size: {stats['total_size_mb']} MB")
        print(f"Raw bytes: {stats['total_size_bytes']}")
        
    except Exception as e:
        print(f"❌ Error getting storage stats: {e}")


async def example_cleanup_operations():
    """Example: Cleanup operations"""
    print("\n🧹 Cleanup Operations Example")
    print("=" * 50)
    
    # Initialize services
    s3_service = create_s3_service(
        bucket_name="echoes-audio-dev",
        region="us-east-1",
        aws_profile=os.getenv("AWS_PROFILE", "default")
    )
    cleanup_service = create_cleanup_service(s3_service)
    
    try:
        # Generate storage report
        print("Generating storage report...")
        report = await cleanup_service.get_storage_report("user123")
        
        print(f"📈 Storage Report:")
        print(f"   S3 Files: {report['s3_storage']['total_files']}")
        print(f"   S3 Size: {report['s3_storage']['total_size_mb']} MB")
        print(f"   DB Echoes: {report['db_echo_count']}")
        print(f"   Old Echoes: {report['old_echoes_count']}")
        
        # File integrity check
        print("\nChecking file integrity...")
        integrity = await cleanup_service.verify_file_integrity("user123")
        
        print(f"🔍 Integrity Report:")
        print(f"   Total echoes: {integrity['total_echoes']}")
        print(f"   Verified files: {integrity['verified_files']}")
        print(f"   Missing files: {integrity['missing_files']}")
        print(f"   Errors: {integrity['errors']}")
        
        if integrity['missing_files_details']:
            print("   Missing files:")
            for missing in integrity['missing_files_details'][:3]:  # Show first 3
                print(f"     - {missing['s3_key']}")
        
    except Exception as e:
        print(f"❌ Error with cleanup operations: {e}")


async def example_validation():
    """Example: Audio file validation"""
    print("\n✅ Validation Example")
    print("=" * 50)
    
    s3_service = create_s3_service(
        bucket_name="echoes-audio-dev",
        region="us-east-1",
        aws_profile=os.getenv("AWS_PROFILE", "default")
    )
    
    # Test valid formats
    valid_formats = [
        ("webm", "audio/webm"),
        ("mp3", "audio/mpeg"),
        ("wav", "audio/wav"),
        ("m4a", "audio/mp4"),
        ("ogg", "audio/ogg")
    ]
    
    print("Testing valid formats:")
    for ext, content_type in valid_formats:
        try:
            s3_service.validate_audio_file(ext, content_type)
            print(f"   ✅ {ext} ({content_type}) - Valid")
        except ValueError as e:
            print(f"   ❌ {ext} ({content_type}) - Invalid: {e}")
    
    # Test invalid formats
    invalid_formats = [
        ("txt", "text/plain"),
        ("mp4", "video/mp4"),
        ("webm", "audio/mp3"),  # Mismatched
    ]
    
    print("\nTesting invalid formats:")
    for ext, content_type in invalid_formats:
        try:
            s3_service.validate_audio_file(ext, content_type)
            print(f"   ❌ {ext} ({content_type}) - Should be invalid!")
        except ValueError as e:
            print(f"   ✅ {ext} ({content_type}) - Correctly rejected: {e}")


async def example_key_generation():
    """Example: S3 key generation with timestamp structure"""
    print("\n🗝️  Key Generation Example")
    print("=" * 50)
    
    s3_service = create_s3_service(
        bucket_name="echoes-audio-dev",
        region="us-east-1"
    )
    
    # Generate keys for different scenarios
    scenarios = [
        ("user123", "webm", None),
        ("user456", "mp3", "custom-echo-id-123"),
        ("user789", "wav", None)
    ]
    
    for user_id, ext, echo_id in scenarios:
        s3_key, generated_echo_id = s3_service.generate_s3_key(user_id, ext, echo_id)
        print(f"User: {user_id}")
        print(f"   Input echo_id: {echo_id or 'auto-generated'}")
        print(f"   Generated echo_id: {generated_echo_id}")
        print(f"   S3 key: {s3_key}")
        print()


def show_configuration_help():
    """Show configuration help"""
    print("\n⚙️  Configuration Help")
    print("=" * 50)
    
    print("Environment Variables:")
    print("   AWS_PROFILE - AWS profile name for credentials")
    print("   AWS_REGION  - AWS region (default: us-east-1)")
    print()
    
    print("Example setup:")
    print("   export AWS_PROFILE=my-profile")
    print("   export AWS_REGION=us-west-2")
    print()
    
    print("AWS Profile setup:")
    print("   aws configure --profile my-profile")
    print()


async def main():
    """Run all examples"""
    print("🎵 Echoes S3 Service Usage Examples")
    print("=" * 60)
    
    # Check if AWS profile is configured
    aws_profile = os.getenv("AWS_PROFILE", "default")
    print(f"Using AWS profile: {aws_profile}")
    print()
    
    try:
        # Run examples
        await example_presigned_url_generation()
        await example_file_operations()
        await example_storage_statistics()
        await example_cleanup_operations()
        await example_validation()
        await example_key_generation()
        
        print("\n🎉 All examples completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure AWS credentials are configured")
        print("2. Check that the S3 bucket exists")
        print("3. Verify bucket permissions")
        
        show_configuration_help()


if __name__ == "__main__":
    # Check for help flag
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help"]:
        show_configuration_help()
        sys.exit(0)
    
    # Run examples
    asyncio.run(main())