# Echoes DynamoDB Database Schema Design

## Table: EchoesTable

### Primary Key Structure
- **Partition Key (PK)**: `userId` (String)
- **Sort Key (SK)**: `timestamp` (String) - ISO 8601 format
- **Unique Identifier**: `echoId` (String) - UUID for direct access

### Complete Schema

```json
{
  "TableName": "EchoesTable",
  "KeySchema": [
    {
      "AttributeName": "userId",
      "KeyType": "HASH"
    },
    {
      "AttributeName": "timestamp", 
      "KeyType": "RANGE"
    }
  ],
  "AttributeDefinitions": [
    {
      "AttributeName": "userId",
      "AttributeType": "S"
    },
    {
      "AttributeName": "timestamp",
      "AttributeType": "S"
    },
    {
      "AttributeName": "emotion",
      "AttributeType": "S"
    },
    {
      "AttributeName": "echoId",
      "AttributeType": "S"
    }
  ],
  "BillingMode": "PAY_PER_REQUEST"
}
```

### Item Structure

```json
{
  "userId": {
    "S": "abc123"
  },
  "timestamp": {
    "S": "2025-06-25T15:00:00.000Z"
  },
  "echoId": {
    "S": "echo_01HZ8X4K7N2M6P8Q9R3S5T7V"
  },
  "emotion": {
    "S": "Calm"
  },
  "s3Url": {
    "S": "s3://echoes-audio-prod/abc123/echo_01HZ8X4K7N2M6P8Q9R3S5T7V.webm"
  },
  "location": {
    "M": {
      "lat": {
        "N": "37.5407"
      },
      "lng": {
        "N": "-77.4360"
      }
    }
  },
  "tags": {
    "L": [
      {"S": "river"},
      {"S": "kids"},
      {"S": "outdoors"}
    ]
  },
  "transcript": {
    "S": "Rio laughing and water splashing"
  },
  "detectedMood": {
    "S": "joy"
  },
  "createdAt": {
    "S": "2025-06-25T15:00:00.000Z"
  },
  "updatedAt": {
    "S": "2025-06-25T15:00:00.000Z"
  },
  "version": {
    "N": "1"
  },
  "metadata": {
    "M": {
      "duration": {
        "N": "23.5"
      },
      "fileSize": {
        "N": "1048576"
      },
      "audioFormat": {
        "S": "webm"
      },
      "transcriptionConfidence": {
        "N": "0.95"
      }
    }
  }
}
```

## Global Secondary Indexes (GSI)

### GSI 1: Emotion-Timestamp Index
**Purpose**: Query echoes by emotion across all users, sorted by time

```json
{
  "IndexName": "emotion-timestamp-index",
  "KeySchema": [
    {
      "AttributeName": "emotion",
      "KeyType": "HASH"
    },
    {
      "AttributeName": "timestamp",
      "KeyType": "RANGE"
    }
  ],
  "Projection": {
    "ProjectionType": "ALL"
  },
  "BillingMode": "PAY_PER_REQUEST"
}
```

### GSI 2: EchoId Index
**Purpose**: Direct access to echoes by echoId (for sharing, direct links)

```json
{
  "IndexName": "echoId-index", 
  "KeySchema": [
    {
      "AttributeName": "echoId",
      "KeyType": "HASH"
    }
  ],
  "Projection": {
    "ProjectionType": "ALL"
  },
  "BillingMode": "PAY_PER_REQUEST"
}
```

### GSI 3: User-Emotion Index  
**Purpose**: Query user's echoes filtered by emotion

```json
{
  "IndexName": "userId-emotion-index",
  "KeySchema": [
    {
      "AttributeName": "userId", 
      "KeyType": "HASH"
    },
    {
      "AttributeName": "emotion",
      "KeyType": "RANGE"
    }
  ],
  "Projection": {
    "ProjectionType": "INCLUDE",
    "NonKeyAttributes": [
      "timestamp",
      "echoId", 
      "s3Url",
      "location",
      "tags",
      "detectedMood"
    ]
  },
  "BillingMode": "PAY_PER_REQUEST"
}
```

## Query Patterns

### 1. Get User's Echoes (Chronological)
```python
# Most recent first
response = dynamodb.query(
    TableName='EchoesTable',
    KeyConditionExpression='userId = :userId',
    ExpressionAttributeValues={':userId': {'S': 'abc123'}},
    ScanIndexForward=False,  # Descending order
    Limit=20
)
```

### 2. Get Echoes by Emotion (Global)
```python
# All echoes with specific emotion
response = dynamodb.query(
    TableName='EchoesTable',
    IndexName='emotion-timestamp-index',
    KeyConditionExpression='emotion = :emotion',
    ExpressionAttributeValues={':emotion': {'S': 'Calm'}},
    ScanIndexForward=False
)
```

### 3. Get User's Echoes by Emotion
```python
# User's echoes filtered by emotion
response = dynamodb.query(
    TableName='EchoesTable', 
    IndexName='userId-emotion-index',
    KeyConditionExpression='userId = :userId AND emotion = :emotion',
    ExpressionAttributeValues={
        ':userId': {'S': 'abc123'},
        ':emotion': {'S': 'Calm'}
    }
)
```

### 4. Get Random Echo by Emotion
```python
# Strategy: Query by emotion, use random offset
import random

# First get count
count_response = dynamodb.query(
    TableName='EchoesTable',
    IndexName='emotion-timestamp-index', 
    KeyConditionExpression='emotion = :emotion',
    ExpressionAttributeValues={':emotion': {'S': 'Calm'}},
    Select='COUNT'
)

# Then get random item
random_offset = random.randint(0, count_response['Count'] - 1)
response = dynamodb.query(
    TableName='EchoesTable',
    IndexName='emotion-timestamp-index',
    KeyConditionExpression='emotion = :emotion', 
    ExpressionAttributeValues={':emotion': {'S': 'Calm'}},
    Limit=1,
    ExclusiveStartKey=... # Skip to random position
)
```

### 5. Get Specific Echo by ID
```python
# Direct access by echoId
response = dynamodb.query(
    TableName='EchoesTable',
    IndexName='echoId-index',
    KeyConditionExpression='echoId = :echoId',
    ExpressionAttributeValues={':echoId': {'S': 'echo_01HZ8X4K7N2M6P8Q9R3S5T7V'}}
)
```

### 6. Time Range Queries
```python
# User's echoes in date range
response = dynamodb.query(
    TableName='EchoesTable',
    KeyConditionExpression='userId = :userId AND #ts BETWEEN :start AND :end',
    ExpressionAttributeNames={'#ts': 'timestamp'},
    ExpressionAttributeValues={
        ':userId': {'S': 'abc123'},
        ':start': {'S': '2025-06-01T00:00:00.000Z'},
        ':end': {'S': '2025-06-30T23:59:59.999Z'}
    }
)
```

## Design Decisions & Rationale

### 1. Partition Key: userId
- **Benefits**: 
  - Natural data isolation per user
  - Efficient queries for user's echoes
  - Supports user-level access patterns
- **Considerations**:
  - Hot partitions if users are very active
  - Mitigated by time-based sort key spreading writes

### 2. Sort Key: timestamp
- **Benefits**:
  - Natural chronological ordering
  - Efficient time-range queries
  - Supports pagination by time
- **Alternative Considered**: echoId as sort key
  - Would require timestamp as GSI
  - Less efficient for primary use case (chronological access)

### 3. Multiple GSI Strategy
- **emotion-timestamp-index**: Global emotion queries
- **echoId-index**: Direct echo access (sharing, APIs)
- **userId-emotion-index**: User's emotion-filtered echoes

### 4. Data Types
- **Strings**: userId, echoId, emotion, timestamp (ISO 8601)
- **Numbers**: coordinates, metadata values
- **Lists**: tags (flexible tagging)
- **Maps**: location, metadata (structured data)

## Next Steps
1. Implement Global Secondary Indexes
2. Define scaling and optimization strategies
3. Create CloudFormation/CDK templates
4. Plan migration scripts