const AWS = require('aws-sdk');
const dynamodb = new AWS.DynamoDB.DocumentClient();
const { v4: uuidv4 } = require('uuid');

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
    const {
      echoId,
      emotion,
      location,
      tags = [],
      transcript = '',
      s3Url,
      fileType = 'webm',
      duration,
      title,
      description,
    } = body;

    // Validate required fields
    if (!echoId || !emotion) {
      return {
        statusCode: 400,
        headers,
        body: JSON.stringify({ error: 'echoId and emotion are required' }),
      };
    }

    // Validate emotion
    const validEmotions = [
      'joy', 'calm', 'excited', 'nostalgic', 'peaceful', 'energetic',
      'melancholy', 'hopeful', 'grateful', 'contemplative', 'love',
      'anxious', 'sad', 'angry', 'frustrated', 'overwhelmed'
    ];
    
    if (!validEmotions.includes(emotion.toLowerCase())) {
      return {
        statusCode: 400,
        headers,
        body: JSON.stringify({ 
          error: 'Invalid emotion. Valid emotions: ' + validEmotions.join(', ') 
        }),
      };
    }

    // Create echo item
    const timestamp = new Date().toISOString();
    const echoItem = {
      userId,
      echoId,
      emotion: emotion.toLowerCase(),
      timestamp,
      s3Url: s3Url || `s3://${process.env.AUDIOS_BUCKET_NAME}/${userId}/${echoId}.${fileType}`,
      fileType,
      duration: duration || null,
      title: title || null,
      description: description || null,
      location: location ? {
        lat: parseFloat(location.lat),
        lng: parseFloat(location.lng),
        address: location.address || null,
      } : null,
      tags: Array.isArray(tags) ? tags.filter(tag => typeof tag === 'string' && tag.length > 0) : [],
      transcript: transcript || '',
      detectedMood: null, // To be filled by AI processing later
      createdAt: timestamp,
      updatedAt: timestamp,
      isActive: true,
      playCount: 0,
      lastPlayedAt: null,
      nextNotificationTime: null, // For future notification features
    };

    // Save to DynamoDB
    const params = {
      TableName: process.env.ECHOES_TABLE_NAME,
      Item: echoItem,
      ConditionExpression: 'attribute_not_exists(echoId)', // Prevent overwriting
    };

    await dynamodb.put(params).promise();

    console.log(`Echo saved successfully: ${echoId} for user: ${userId}`);

    return {
      statusCode: 201,
      headers,
      body: JSON.stringify({
        message: 'Echo saved successfully',
        echo: echoItem,
      }),
    };
  } catch (error) {
    console.error('Error saving echo:', error);
    
    // Handle conditional check failure (duplicate echoId)
    if (error.code === 'ConditionalCheckFailedException') {
      return {
        statusCode: 409,
        headers,
        body: JSON.stringify({ error: 'Echo with this ID already exists' }),
      };
    }

    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({ error: 'Internal server error' }),
    };
  }
};