const AWS = require('aws-sdk');
const dynamodb = new AWS.DynamoDB.DocumentClient();

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

    // Parse query parameters
    const queryParams = event.queryStringParameters || {};
    const {
      emotion,
      excludeRecent = 'false',
      minDaysOld = '0',
      tags,
    } = queryParams;

    const minDaysOldNum = parseInt(minDaysOld, 10);
    const excludeRecentBool = excludeRecent === 'true';

    let params;
    let indexName = null;

    if (emotion) {
      // Query by emotion using GSI
      indexName = 'userId-emotion-index';
      params = {
        TableName: process.env.ECHOES_TABLE_NAME,
        IndexName: indexName,
        KeyConditionExpression: 'userId = :userId AND emotion = :emotion',
        ExpressionAttributeValues: {
          ':userId': userId,
          ':emotion': emotion.toLowerCase(),
          ':isActive': true,
        },
        FilterExpression: 'isActive = :isActive',
      };
    } else {
      // Get all echoes for user
      params = {
        TableName: process.env.ECHOES_TABLE_NAME,
        KeyConditionExpression: 'userId = :userId',
        ExpressionAttributeValues: {
          ':userId': userId,
          ':isActive': true,
        },
        FilterExpression: 'isActive = :isActive',
      };
    }

    // Add time-based filters
    if (excludeRecentBool || minDaysOldNum > 0) {
      const cutoffDate = new Date();
      cutoffDate.setDate(cutoffDate.getDate() - Math.max(minDaysOldNum, excludeRecentBool ? 7 : 0));
      
      params.ExpressionAttributeValues[':cutoffDate'] = cutoffDate.toISOString();
      params.FilterExpression += ' AND #timestamp < :cutoffDate';
      params.ExpressionAttributeNames = {
        '#timestamp': 'timestamp',
      };
    }

    // Add tags filter if provided
    if (tags) {
      const tagArray = tags.split(',').map(tag => tag.trim());
      const tagFilters = tagArray.map((_, index) => `contains(tags, :tag${index})`).join(' OR ');
      
      tagArray.forEach((tag, index) => {
        params.ExpressionAttributeValues[`:tag${index}`] = tag;
      });
      
      params.FilterExpression += ` AND (${tagFilters})`;
    }

    // Execute query to get all matching echoes
    const result = await dynamodb.query(params).promise();

    if (!result.Items || result.Items.length === 0) {
      return {
        statusCode: 404,
        headers,
        body: JSON.stringify({ 
          error: 'No echoes found matching the criteria',
          criteria: {
            emotion,
            excludeRecent: excludeRecentBool,
            minDaysOld: minDaysOldNum,
            tags,
          },
        }),
      };
    }

    // Implement weighted random selection
    // Older echoes get higher weight for "rediscovery" effect
    const now = new Date();
    const echoesWithWeights = result.Items.map(echo => {
      const echoDate = new Date(echo.timestamp);
      const daysOld = Math.floor((now - echoDate) / (1000 * 60 * 60 * 24));
      
      // Weight formula: older echoes get higher weight, but not too extreme
      // Also consider play count (less played = higher weight)
      const ageWeight = Math.min(daysOld * 0.1 + 1, 5); // Max weight of 5
      const playWeight = Math.max(1 - (echo.playCount || 0) * 0.1, 0.1); // Min weight of 0.1
      const totalWeight = ageWeight * playWeight;
      
      return {
        echo,
        weight: totalWeight,
      };
    });

    // Calculate cumulative weights
    const totalWeight = echoesWithWeights.reduce((sum, item) => sum + item.weight, 0);
    const randomValue = Math.random() * totalWeight;
    
    let cumulativeWeight = 0;
    let selectedEcho = null;
    
    for (const item of echoesWithWeights) {
      cumulativeWeight += item.weight;
      if (randomValue <= cumulativeWeight) {
        selectedEcho = item.echo;
        break;
      }
    }

    // Fallback to first echo if something goes wrong
    if (!selectedEcho) {
      selectedEcho = echoesWithWeights[0].echo;
    }

    // Generate presigned URL for the selected echo
    const s3 = new AWS.S3();
    let audioUrl = null;
    
    try {
      const s3Key = selectedEcho.s3Url.replace(`s3://${process.env.AUDIOS_BUCKET_NAME}/`, '');
      audioUrl = await s3.getSignedUrlPromise('getObject', {
        Bucket: process.env.AUDIOS_BUCKET_NAME,
        Key: s3Key,
        Expires: 3600, // 1 hour
      });
    } catch (error) {
      console.error(`Error generating presigned URL for echo ${selectedEcho.echoId}:`, error);
    }

    // Update play count
    try {
      await dynamodb.update({
        TableName: process.env.ECHOES_TABLE_NAME,
        Key: {
          userId: selectedEcho.userId,
          echoId: selectedEcho.echoId,
        },
        UpdateExpression: 'SET playCount = if_not_exists(playCount, :zero) + :one, lastPlayedAt = :now',
        ExpressionAttributeValues: {
          ':zero': 0,
          ':one': 1,
          ':now': new Date().toISOString(),
        },
      }).promise();
    } catch (error) {
      console.error('Error updating play count:', error);
      // Don't fail the request if we can't update the play count
    }

    // Prepare response
    const response = {
      echo: {
        ...selectedEcho,
        audioUrl,
        playCount: (selectedEcho.playCount || 0) + 1,
        lastPlayedAt: new Date().toISOString(),
      },
      totalMatching: result.Items.length,
      selectionCriteria: {
        emotion,
        excludeRecent: excludeRecentBool,
        minDaysOld: minDaysOldNum,
        tags,
      },
    };

    return {
      statusCode: 200,
      headers,
      body: JSON.stringify(response),
    };
  } catch (error) {
    console.error('Error fetching random echo:', error);
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({ error: 'Internal server error' }),
    };
  }
};