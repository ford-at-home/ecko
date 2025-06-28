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
      limit = '20',
      lastEvaluatedKey,
      sortBy = 'timestamp',
      sortOrder = 'desc',
      tags,
      startDate,
      endDate,
    } = queryParams;

    const limitNum = parseInt(limit, 10);
    if (limitNum > 100) {
      return {
        statusCode: 400,
        headers,
        body: JSON.stringify({ error: 'Limit cannot exceed 100' }),
      };
    }

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
        ScanIndexForward: sortOrder === 'asc',
        Limit: limitNum,
      };
    } else {
      // Query all echoes for user
      params = {
        TableName: process.env.ECHOES_TABLE_NAME,
        KeyConditionExpression: 'userId = :userId',
        ExpressionAttributeValues: {
          ':userId': userId,
          ':isActive': true,
        },
        FilterExpression: 'isActive = :isActive',
        ScanIndexForward: sortOrder === 'asc',
        Limit: limitNum,
      };
    }

    // Add date range filter if provided
    if (startDate || endDate) {
      let dateFilter = '';
      if (startDate) {
        params.ExpressionAttributeValues[':startDate'] = startDate;
        dateFilter += '#timestamp >= :startDate';
      }
      if (endDate) {
        params.ExpressionAttributeValues[':endDate'] = endDate;
        if (dateFilter) dateFilter += ' AND ';
        dateFilter += '#timestamp <= :endDate';
      }
      
      if (dateFilter) {
        params.FilterExpression += ` AND (${dateFilter})`;
        params.ExpressionAttributeNames = {
          '#timestamp': 'timestamp',
        };
      }
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

    // Handle pagination
    if (lastEvaluatedKey) {
      try {
        params.ExclusiveStartKey = JSON.parse(decodeURIComponent(lastEvaluatedKey));
      } catch (error) {
        console.error('Invalid lastEvaluatedKey:', error);
        return {
          statusCode: 400,
          headers,
          body: JSON.stringify({ error: 'Invalid pagination key' }),
        };
      }
    }

    // Execute query
    const result = await dynamodb.query(params).promise();

    // Generate presigned URLs for S3 objects
    const s3 = new AWS.S3();
    const echoesWithUrls = await Promise.all(
      result.Items.map(async (echo) => {
        try {
          // Extract S3 key from s3Url
          const s3Key = echo.s3Url.replace(`s3://${process.env.AUDIOS_BUCKET_NAME}/`, '');
          const presignedUrl = await s3.getSignedUrlPromise('getObject', {
            Bucket: process.env.AUDIOS_BUCKET_NAME,
            Key: s3Key,
            Expires: 3600, // 1 hour
          });
          
          return {
            ...echo,
            audioUrl: presignedUrl,
          };
        } catch (error) {
          console.error(`Error generating presigned URL for echo ${echo.echoId}:`, error);
          return {
            ...echo,
            audioUrl: null,
          };
        }
      })
    );

    // Prepare response
    const response = {
      echoes: echoesWithUrls,
      count: result.Items.length,
      lastEvaluatedKey: result.LastEvaluatedKey 
        ? encodeURIComponent(JSON.stringify(result.LastEvaluatedKey))
        : null,
      hasMore: !!result.LastEvaluatedKey,
    };

    return {
      statusCode: 200,
      headers,
      body: JSON.stringify(response),
    };
  } catch (error) {
    console.error('Error fetching echoes:', error);
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({ error: 'Internal server error' }),
    };
  }
};