import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import {
  DynamoDBDocumentClient,
  PutCommand,
  GetCommand,
  QueryCommand,
  UpdateCommand,
  DeleteCommand,
  ScanCommand,
} from '@aws-sdk/lib-dynamodb';
import { v4 as uuidv4 } from 'uuid';

// Initialize DynamoDB client
const dynamoClient = new DynamoDBClient({
  region: process.env.AWS_REGION || 'us-east-1',
});

const docClient = DynamoDBDocumentClient.from(dynamoClient);

const TABLE_NAME = process.env.DYNAMODB_TABLE_NAME!;

if (!TABLE_NAME) {
  throw new Error('DYNAMODB_TABLE_NAME environment variable is required');
}

export interface Echo {
  userId: string;
  echoId: string;
  emotion: string;
  timestamp: string;
  s3Url: string;
  objectKey: string;
  location?: {
    lat: number;
    lng: number;
    address?: string;
  };
  tags?: string[];
  transcript?: string;
  detectedMood?: string;
  duration?: number;
  fileSize?: number;
  contentType?: string;
  createdAt: string;
  updatedAt?: string;
  version: number;
  ttl?: number;
}

export interface CreateEchoInput {
  userId: string;
  emotion: string;
  s3Url: string;
  objectKey: string;
  location?: Echo['location'];
  tags?: string[];
  transcript?: string;
  detectedMood?: string;
  duration?: number;
  fileSize?: number;
  contentType?: string;
}

export interface QueryEchoesInput {
  userId: string;
  emotion?: string;
  limit?: number;
  lastEvaluatedKey?: any;
}

export interface QueryEchoesResult {
  echoes: Echo[];
  lastEvaluatedKey?: any;
  count: number;
}

/**
 * Create a new echo in DynamoDB
 */
export async function createEcho(input: CreateEchoInput): Promise<Echo> {
  try {
    const echoId = uuidv4();
    const timestamp = new Date().toISOString();
    const createdAt = timestamp;
    
    // Calculate TTL (5 years from creation)
    const ttl = Math.floor(Date.now() / 1000) + (5 * 365 * 24 * 60 * 60);

    const echo: Echo = {
      userId: input.userId,
      echoId,
      emotion: input.emotion,
      timestamp,
      s3Url: input.s3Url,
      objectKey: input.objectKey,
      location: input.location,
      tags: input.tags || [],
      transcript: input.transcript || '',
      detectedMood: input.detectedMood || '',
      duration: input.duration || 0,
      fileSize: input.fileSize || 0,
      contentType: input.contentType || 'audio/webm',
      createdAt,
      version: 1,
      ttl,
    };

    const command = new PutCommand({
      TableName: TABLE_NAME,
      Item: echo,
      ConditionExpression: 'attribute_not_exists(echoId)',
    });

    await docClient.send(command);
    console.log(`Successfully created echo: ${echoId}`);
    
    return echo;
  } catch (error) {
    console.error('Error creating echo:', error);
    throw new Error('Failed to create echo');
  }
}

/**
 * Get a specific echo by user ID and echo ID
 */
export async function getEcho(userId: string, echoId: string): Promise<Echo | null> {
  try {
    const command = new GetCommand({
      TableName: TABLE_NAME,
      Key: {
        userId,
        echoId,
      },
    });

    const result = await docClient.send(command);
    return result.Item as Echo || null;
  } catch (error) {
    console.error('Error getting echo:', error);
    throw new Error('Failed to get echo');
  }
}

/**
 * Query echoes for a user, optionally filtered by emotion
 */
export async function queryUserEchoes(input: QueryEchoesInput): Promise<QueryEchoesResult> {
  try {
    let command;

    if (input.emotion) {
      // Query by emotion using GSI
      command = new QueryCommand({
        TableName: TABLE_NAME,
        IndexName: 'emotion-timestamp-index',
        KeyConditionExpression: 'emotion = :emotion',
        FilterExpression: 'userId = :userId',
        ExpressionAttributeValues: {
          ':emotion': input.emotion,
          ':userId': input.userId,
        },
        ScanIndexForward: false, // Sort by timestamp descending
        Limit: input.limit || 50,
        ExclusiveStartKey: input.lastEvaluatedKey,
      });
    } else {
      // Query by user ID
      command = new QueryCommand({
        TableName: TABLE_NAME,
        KeyConditionExpression: 'userId = :userId',
        ExpressionAttributeValues: {
          ':userId': input.userId,
        },
        ScanIndexForward: false, // Sort by echoId descending
        Limit: input.limit || 50,
        ExclusiveStartKey: input.lastEvaluatedKey,
      });
    }

    const result = await docClient.send(command);
    
    return {
      echoes: result.Items as Echo[] || [],
      lastEvaluatedKey: result.LastEvaluatedKey,
      count: result.Count || 0,
    };
  } catch (error) {
    console.error('Error querying user echoes:', error);
    throw new Error('Failed to query echoes');
  }
}

/**
 * Get a random echo for a user, optionally filtered by emotion
 */
export async function getRandomEcho(userId: string, emotion?: string): Promise<Echo | null> {
  try {
    let echoes: Echo[];

    if (emotion) {
      // Query by emotion
      const result = await queryUserEchoes({ userId, emotion, limit: 100 });
      echoes = result.echoes;
    } else {
      // Query all user echoes
      const result = await queryUserEchoes({ userId, limit: 100 });
      echoes = result.echoes;
    }

    if (echoes.length === 0) {
      return null;
    }

    // Return a random echo
    const randomIndex = Math.floor(Math.random() * echoes.length);
    return echoes[randomIndex];
  } catch (error) {
    console.error('Error getting random echo:', error);
    throw new Error('Failed to get random echo');
  }
}

/**
 * Update an echo
 */
export async function updateEcho(
  userId: string,
  echoId: string,
  updates: Partial<Omit<Echo, 'userId' | 'echoId' | 'createdAt' | 'version'>>
): Promise<Echo> {
  try {
    const updatedAt = new Date().toISOString();
    
    // Build update expression
    const updateExpressions = [];
    const expressionAttributeValues: any = {};
    const expressionAttributeNames: any = {};

    for (const [key, value] of Object.entries(updates)) {
      if (value !== undefined) {
        updateExpressions.push(`#${key} = :${key}`);
        expressionAttributeValues[`:${key}`] = value;
        expressionAttributeNames[`#${key}`] = key;
      }
    }

    // Always update version and updatedAt
    updateExpressions.push('#version = #version + :inc', '#updatedAt = :updatedAt');
    expressionAttributeValues[':inc'] = 1;
    expressionAttributeValues[':updatedAt'] = updatedAt;
    expressionAttributeNames['#version'] = 'version';
    expressionAttributeNames['#updatedAt'] = 'updatedAt';

    const command = new UpdateCommand({
      TableName: TABLE_NAME,
      Key: {
        userId,
        echoId,
      },
      UpdateExpression: `SET ${updateExpressions.join(', ')}`,
      ExpressionAttributeValues: expressionAttributeValues,
      ExpressionAttributeNames: expressionAttributeNames,
      ConditionExpression: 'attribute_exists(echoId)',
      ReturnValues: 'ALL_NEW',
    });

    const result = await docClient.send(command);
    return result.Attributes as Echo;
  } catch (error) {
    console.error('Error updating echo:', error);
    throw new Error('Failed to update echo');
  }
}

/**
 * Delete an echo
 */
export async function deleteEcho(userId: string, echoId: string): Promise<void> {
  try {
    const command = new DeleteCommand({
      TableName: TABLE_NAME,
      Key: {
        userId,
        echoId,
      },
      ConditionExpression: 'attribute_exists(echoId)',
    });

    await docClient.send(command);
    console.log(`Successfully deleted echo: ${echoId}`);
  } catch (error) {
    console.error('Error deleting echo:', error);
    throw new Error('Failed to delete echo');
  }
}

/**
 * Get echoes by emotion across all users (for global statistics)
 */
export async function getEchoesByEmotion(emotion: string, limit: number = 50): Promise<Echo[]> {
  try {
    const command = new QueryCommand({
      TableName: TABLE_NAME,
      IndexName: 'emotion-timestamp-index',
      KeyConditionExpression: 'emotion = :emotion',
      ExpressionAttributeValues: {
        ':emotion': emotion,
      },
      ScanIndexForward: false,
      Limit: limit,
    });

    const result = await docClient.send(command);
    return result.Items as Echo[] || [];
  } catch (error) {
    console.error('Error getting echoes by emotion:', error);
    throw new Error('Failed to get echoes by emotion');
  }
}

/**
 * Get DynamoDB configuration
 */
export function getDynamoConfig() {
  return {
    tableName: TABLE_NAME,
    region: process.env.AWS_REGION || 'us-east-1',
    ttlDuration: 5 * 365 * 24 * 60 * 60, // 5 years in seconds
    defaultLimit: 50,
    maxLimit: 100,
  };
}