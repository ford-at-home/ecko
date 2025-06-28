import { S3Client, PutObjectCommand, GetObjectCommand, DeleteObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';
import { v4 as uuidv4 } from 'uuid';

// Initialize S3 client
const s3Client = new S3Client({
  region: process.env.AWS_REGION || 'us-east-1',
});

const BUCKET_NAME = process.env.S3_BUCKET_NAME!;
const PRESIGNED_URL_EXPIRY = 3600; // 1 hour in seconds

if (!BUCKET_NAME) {
  throw new Error('S3_BUCKET_NAME environment variable is required');
}

export interface PresignedUploadResult {
  uploadUrl: string;
  key: string;
  echoId: string;
  bucket: string;
}

export interface PresignedDownloadResult {
  downloadUrl: string;
  key: string;
  bucket: string;
}

/**
 * Generate a presigned URL for uploading audio files
 * Files are stored with user-specific prefixes: {userId}/{echoId}.{extension}
 */
export async function generatePresignedUploadUrl(
  userId: string,
  fileExtension: string = 'webm',
  contentType: string = 'audio/webm'
): Promise<PresignedUploadResult> {
  try {
    const echoId = uuidv4();
    const key = `${userId}/${echoId}.${fileExtension}`;

    const command = new PutObjectCommand({
      Bucket: BUCKET_NAME,
      Key: key,
      ContentType: contentType,
      // Add metadata
      Metadata: {
        userId,
        echoId,
        uploadedAt: new Date().toISOString(),
      },
      // Server-side encryption
      ServerSideEncryption: 'AES256',
    });

    const uploadUrl = await getSignedUrl(s3Client, command, {
      expiresIn: PRESIGNED_URL_EXPIRY,
    });

    return {
      uploadUrl,
      key,
      echoId,
      bucket: BUCKET_NAME,
    };
  } catch (error) {
    console.error('Error generating presigned upload URL:', error);
    throw new Error('Failed to generate upload URL');
  }
}

/**
 * Generate a presigned URL for downloading audio files
 * Validates that the file belongs to the requesting user
 */
export async function generatePresignedDownloadUrl(
  userId: string,
  objectKey: string
): Promise<PresignedDownloadResult> {
  try {
    // Validate that the object key starts with the user's ID
    if (!objectKey.startsWith(`${userId}/`)) {
      throw new Error('Access denied: Object does not belong to user');
    }

    const command = new GetObjectCommand({
      Bucket: BUCKET_NAME,
      Key: objectKey,
    });

    const downloadUrl = await getSignedUrl(s3Client, command, {
      expiresIn: PRESIGNED_URL_EXPIRY,
    });

    return {
      downloadUrl,
      key: objectKey,
      bucket: BUCKET_NAME,
    };
  } catch (error) {
    console.error('Error generating presigned download URL:', error);
    throw new Error('Failed to generate download URL');
  }
}

/**
 * Delete an audio file from S3
 * Validates that the file belongs to the requesting user
 */
export async function deleteAudioFile(
  userId: string,
  objectKey: string
): Promise<void> {
  try {
    // Validate that the object key starts with the user's ID
    if (!objectKey.startsWith(`${userId}/`)) {
      throw new Error('Access denied: Object does not belong to user');
    }

    const command = new DeleteObjectCommand({
      Bucket: BUCKET_NAME,
      Key: objectKey,
    });

    await s3Client.send(command);
    console.log(`Successfully deleted object: ${objectKey}`);
  } catch (error) {
    console.error('Error deleting audio file:', error);
    throw new Error('Failed to delete audio file');
  }
}

/**
 * Validate file extension and content type
 */
export function validateAudioFile(fileName: string, contentType: string): boolean {
  const allowedExtensions = ['webm', 'mp3', 'wav', 'm4a', 'ogg'];
  const allowedContentTypes = [
    'audio/webm',
    'audio/mpeg',
    'audio/mp3',
    'audio/wav',
    'audio/x-wav',
    'audio/mp4',
    'audio/m4a',
    'audio/ogg',
  ];

  const extension = fileName.split('.').pop()?.toLowerCase();
  
  return (
    extension !== undefined &&
    allowedExtensions.includes(extension) &&
    allowedContentTypes.includes(contentType.toLowerCase())
  );
}

/**
 * Get object key from S3 URL
 */
export function extractKeyFromS3Url(s3Url: string): string | null {
  try {
    // Handle both s3:// and https:// URLs
    if (s3Url.startsWith('s3://')) {
      const url = new URL(s3Url);
      return url.pathname.substring(1); // Remove leading slash
    } else if (s3Url.includes('.s3.') || s3Url.includes('.s3-')) {
      const url = new URL(s3Url);
      return url.pathname.substring(1); // Remove leading slash
    }
    return null;
  } catch (error) {
    console.error('Error extracting key from S3 URL:', error);
    return null;
  }
}

/**
 * Generate S3 URL from bucket and key
 */
export function generateS3Url(bucket: string, key: string): string {
  return `s3://${bucket}/${key}`;
}

/**
 * Calculate file size limits
 */
export const FILE_SIZE_LIMITS = {
  MAX_AUDIO_SIZE: 50 * 1024 * 1024, // 50MB
  MAX_DURATION: 600, // 10 minutes in seconds
} as const;

/**
 * S3 configuration for different environments
 */
export function getS3Config() {
  return {
    bucketName: BUCKET_NAME,
    region: process.env.AWS_REGION || 'us-east-1',
    presignedUrlExpiry: PRESIGNED_URL_EXPIRY,
    maxFileSize: FILE_SIZE_LIMITS.MAX_AUDIO_SIZE,
    maxDuration: FILE_SIZE_LIMITS.MAX_DURATION,
    allowedExtensions: ['webm', 'mp3', 'wav', 'm4a', 'ogg'],
    allowedContentTypes: [
      'audio/webm',
      'audio/mpeg',
      'audio/mp3',
      'audio/wav',
      'audio/x-wav',
      'audio/mp4',
      'audio/m4a',
      'audio/ogg',
    ],
  };
}