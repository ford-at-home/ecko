const AWS = require('aws-sdk');
const s3 = new AWS.S3();

exports.handler = async (event) => {
  const headers = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
    'Access-Control-Allow-Methods': 'OPTIONS,POST,GET',
  };

  try {
    // Handle preflight requests
    if (event.httpMethod === 'OPTIONS') {
      return {
        statusCode: 200,
        headers,
        body: JSON.stringify({ message: 'CORS preflight successful' }),
      };
    }

    // Get user ID from Cognito identity
    const userId = event.requestContext?.identity?.cognitoIdentityId;
    if (!userId) {
      return {
        statusCode: 401,
        headers,
        body: JSON.stringify({ error: 'Unauthorized - No user identity found' }),
      };
    }

    // Parse request body
    const body = JSON.parse(event.body || '{}');
    const { echoId, fileType = 'webm', contentType = 'audio/webm' } = body;

    if (!echoId) {
      return {
        statusCode: 400,
        headers,
        body: JSON.stringify({ error: 'echoId is required' }),
      };
    }

    // Validate file type
    const allowedTypes = ['webm', 'mp3', 'wav', 'm4a'];
    if (!allowedTypes.includes(fileType)) {
      return {
        statusCode: 400,
        headers,
        body: JSON.stringify({ error: 'Invalid file type. Allowed types: ' + allowedTypes.join(', ') }),
      };
    }

    // Generate S3 key
    const s3Key = `${userId}/${echoId}.${fileType}`;
    const bucketName = process.env.AUDIOS_BUCKET_NAME;

    // Generate presigned URL for PUT operation
    const presignedUrl = await s3.getSignedUrlPromise('putObject', {
      Bucket: bucketName,
      Key: s3Key,
      ContentType: contentType,
      Expires: 300, // 5 minutes
      Metadata: {
        userId,
        echoId,
        uploadedAt: new Date().toISOString(),
      },
    });

    // Return presigned URL and S3 details
    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({
        presignedUrl,
        s3Key,
        bucketName,
        userId,
        echoId,
        expiresIn: 300,
      }),
    };
  } catch (error) {
    console.error('Error generating presigned URL:', error);
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({ error: 'Internal server error' }),
    };
  }
};