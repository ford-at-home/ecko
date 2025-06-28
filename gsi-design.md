# Global Secondary Index (GSI) Design for EchoesTable

## Overview
The EchoesTable requires multiple GSIs to support efficient querying patterns for emotion-based filtering, direct echo access, and cross-user queries while maintaining optimal performance at scale.

## GSI Design Strategy

### 1. Emotion-Timestamp Index (emotion-timestamp-index)
**Primary Use Case**: Global emotion-based queries across all users

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
  "AttributeDefinitions": [
    {
      "AttributeName": "emotion",
      "AttributeType": "S"
    },
    {
      "AttributeName": "timestamp",
      "AttributeType": "S"
    }
  ],
  "Projection": {
    "ProjectionType": "ALL"
  },
  "BillingMode": "PAY_PER_REQUEST"
}
```

**Query Patterns Supported**:
- `GET /echoes?emotion=joy` - All echoes with specific emotion
- `GET /echoes/random?emotion=joy` - Random echo selection by emotion
- Time-based emotion queries (e.g., "calm echoes from last month")

**Performance Characteristics**:
- **Partition Distribution**: Well-distributed across emotion types
- **Hot Partitions**: Mitigated by timestamp sort key spreading queries
- **Query Efficiency**: O(log n) for emotion + time range queries

### 2. EchoId Index (echoId-index)
**Primary Use Case**: Direct echo access by unique identifier

```json
{
  "IndexName": "echoId-index",
  "KeySchema": [
    {
      "AttributeName": "echoId",
      "KeyType": "HASH"
    }
  ],
  "AttributeDefinitions": [
    {
      "AttributeName": "echoId",
      "AttributeType": "S"
    }
  ],
  "Projection": {
    "ProjectionType": "ALL"
  },
  "BillingMode": "PAY_PER_REQUEST"
}
```

**Query Patterns Supported**:
- Direct echo retrieval for sharing URLs
- API endpoints requiring echo ID lookup
- Echo verification and validation

**Performance Characteristics**:
- **Access Pattern**: Single-item retrieval - O(1)
- **Partition Distribution**: Excellent (UUIDs naturally distributed)
- **Use Case**: High-performance direct access

### 3. User-Emotion Index (userId-emotion-index)
**Primary Use Case**: User's echoes filtered by emotion

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
  "AttributeDefinitions": [
    {
      "AttributeName": "userId",
      "AttributeType": "S"
    },
    {
      "AttributeName": "emotion",
      "AttributeType": "S"
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
      "detectedMood",
      "transcript",
      "metadata"
    ]
  },
  "BillingMode": "PAY_PER_REQUEST"
}
```

**Query Patterns Supported**:
- User's echoes filtered by specific emotion
- Personalized emotion analytics
- User mood tracking over time

**Performance Characteristics**:
- **Partition Key**: userId (good distribution)
- **Sort Key**: emotion (efficient filtering)
- **Projection**: Optimized to include only necessary attributes

## Advanced GSI Patterns

### 4. Composite GSI for Complex Queries (Optional)
For advanced analytics and complex filtering:

```json
{
  "IndexName": "composite-query-index",
  "KeySchema": [
    {
      "AttributeName": "emotion#detectedMood",
      "KeyType": "HASH"
    },
    {
      "AttributeName": "timestamp",
      "KeyType": "RANGE"
    }
  ],
  "AttributeDefinitions": [
    {
      "AttributeName": "emotion#detectedMood",
      "AttributeType": "S"
    },
    {
      "AttributeName": "timestamp",
      "AttributeType": "S"
    }
  ]
}
```

**Use Case**: Query echoes where user emotion differs from AI-detected mood
**Pattern**: `emotion#detectedMood = "happy#sad"` for discrepancy analysis

## GSI Cost Optimization

### Projection Strategies

1. **emotion-timestamp-index**: 
   - Projection: ALL (supports random selection)
   - Justification: Random queries need all attributes

2. **echoId-index**:
   - Projection: ALL (direct access needs complete item)
   - Justification: Primary access pattern for sharing

3. **userId-emotion-index**:
   - Projection: INCLUDE (optimized subset)
   - Justification: Most queries only need core attributes

### Write Cost Management

```python
# Efficient batch writes to minimize GSI updates
def batch_write_echoes(echoes):
    with dynamodb.batch_writer() as batch:
        for echo in echoes:
            # Single write updates all GSIs
            batch.put_item(Item=echo)
```

## Query Optimization Strategies

### 1. Emotion-Based Random Selection
```python
# Optimized random selection using GSI
def get_random_echo_by_emotion(emotion):
    # Use parallel scans for better performance
    scan_segments = 4
    
    # Get random segment
    segment = random.randint(0, scan_segments - 1)
    
    response = dynamodb.scan(
        TableName='EchoesTable',
        IndexName='emotion-timestamp-index',
        FilterExpression='emotion = :emotion',
        ExpressionAttributeValues={':emotion': emotion},
        Segment=segment,
        TotalSegments=scan_segments,
        Limit=1
    )
    
    if response['Items']:
        return random.choice(response['Items'])
    
    # Fallback to query if scan returns empty
    return query_fallback(emotion)
```

### 2. Pagination Optimization
```python
# Efficient pagination using GSI
def get_echoes_by_emotion_paginated(emotion, page_size=20, last_key=None):
    params = {
        'TableName': 'EchoesTable',
        'IndexName': 'emotion-timestamp-index',
        'KeyConditionExpression': 'emotion = :emotion',
        'ExpressionAttributeValues': {':emotion': emotion},
        'Limit': page_size,
        'ScanIndexForward': False  # Most recent first
    }
    
    if last_key:
        params['ExclusiveStartKey'] = last_key
    
    return dynamodb.query(**params)
```

### 3. Composite Query Patterns
```python
# User + emotion queries using specialized GSI
def get_user_echoes_by_emotion(user_id, emotion, limit=50):
    return dynamodb.query(
        TableName='EchoesTable',
        IndexName='userId-emotion-index',
        KeyConditionExpression='userId = :userId AND emotion = :emotion',
        ExpressionAttributeValues={
            ':userId': user_id,
            ':emotion': emotion
        },
        Limit=limit,
        ScanIndexForward=False
    )
```

## Performance Monitoring

### Key Metrics to Track
1. **GSI Throttling**: Monitor throttled requests per GSI
2. **Query Latency**: Track p95/p99 latencies per GSI
3. **Cost per Query**: Monitor RCU/WCU consumption
4. **Hot Partitions**: Identify uneven distribution

### CloudWatch Alarms
```python
# Monitor GSI performance
cloudwatch.put_metric_alarm(
    AlarmName='EchoesTable-GSI-Throttling',
    MetricName='ReadThrottleEvents',
    Namespace='AWS/DynamoDB',
    Dimensions=[
        {'Name': 'TableName', 'Value': 'EchoesTable'},
        {'Name': 'GlobalSecondaryIndexName', 'Value': 'emotion-timestamp-index'}
    ],
    Threshold=1,
    ComparisonOperator='GreaterThanOrEqualToThreshold'
)
```

## Migration Strategy

### Phase 1: Create GSIs
1. Create emotion-timestamp-index
2. Create echoId-index  
3. Validate query patterns

### Phase 2: Optimize
1. Add userId-emotion-index
2. Monitor performance
3. Adjust projections based on usage

### Phase 3: Advanced Features
1. Consider composite indexes for analytics
2. Implement query result caching
3. Add location-based GSIs if needed

## Best Practices

1. **Avoid Over-Indexing**: Only create GSIs for confirmed query patterns
2. **Monitor Costs**: GSIs double write costs, monitor RCU/WCU usage
3. **Projection Optimization**: Use INCLUDE projections when possible
4. **Query Patterns**: Design queries to leverage sort key ranges
5. **Batch Operations**: Use batch writes to minimize GSI update costs

## Testing Strategy

```python
# GSI performance testing
def test_gsi_performance():
    # Test emotion queries
    start_time = time.time()
    result = get_echoes_by_emotion('happy')
    emotion_query_time = time.time() - start_time
    
    # Test direct access
    start_time = time.time()
    result = get_echo_by_id('echo_123')
    direct_access_time = time.time() - start_time
    
    # Test user emotion queries
    start_time = time.time()
    result = get_user_echoes_by_emotion('user_123', 'calm')
    user_emotion_time = time.time() - start_time
    
    return {
        'emotion_query_ms': emotion_query_time * 1000,
        'direct_access_ms': direct_access_time * 1000,
        'user_emotion_ms': user_emotion_time * 1000
    }
```

This GSI design provides comprehensive query support while maintaining optimal performance and cost efficiency for the Echoes application at scale.