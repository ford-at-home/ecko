# Query Patterns and Optimization for EchoesTable

## Core Query Patterns

### 1. Primary Access Patterns

#### Pattern 1: Get User's Echoes (Chronological)
**Use Case**: Main echo list screen, user's personal timeline
**Frequency**: High (every user session)
**Performance Target**: < 100ms

```python
def get_user_echoes(user_id, limit=20, last_key=None):
    """Get user's echoes in chronological order (most recent first)"""
    params = {
        'TableName': 'EchoesTable',
        'KeyConditionExpression': 'userId = :userId',
        'ExpressionAttributeValues': {':userId': user_id},
        'ScanIndexForward': False,  # Descending timestamp order
        'Limit': limit
    }
    
    if last_key:
        params['ExclusiveStartKey'] = last_key
    
    return dynamodb.query(**params)

# Optimization: Use projection to reduce data transfer
def get_user_echoes_summary(user_id, limit=20):
    """Lightweight version for list views"""
    return dynamodb.query(
        TableName='EchoesTable',
        KeyConditionExpression='userId = :userId', 
        ExpressionAttributeValues={':userId': user_id},
        ProjectionExpression='echoId, emotion, #ts, s3Url, tags',
        ExpressionAttributeNames={'#ts': 'timestamp'},
        ScanIndexForward=False,
        Limit=limit
    )
```

#### Pattern 2: Get Echo by ID
**Use Case**: Direct echo access, sharing, playback
**Frequency**: Medium (when sharing/accessing specific echoes)
**Performance Target**: < 50ms

```python
def get_echo_by_id(echo_id):
    """Direct echo access using echoId GSI"""
    response = dynamodb.query(
        TableName='EchoesTable',
        IndexName='echoId-index',
        KeyConditionExpression='echoId = :echoId',
        ExpressionAttributeValues={':echoId': echo_id}
    )
    
    if response['Items']:
        return response['Items'][0]
    return None

# Alternative: If you have userId, use primary table
def get_echo_by_user_and_timestamp(user_id, timestamp):
    """More efficient if userId is available"""
    response = dynamodb.get_item(
        TableName='EchoesTable',
        Key={
            'userId': user_id,
            'timestamp': timestamp
        }
    )
    return response.get('Item')
```

### 2. Emotion-Based Query Patterns

#### Pattern 3: Global Emotion Queries
**Use Case**: "Show me all calm echoes", content discovery
**Frequency**: Medium (exploration features)
**Performance Target**: < 200ms

```python
def get_echoes_by_emotion(emotion, limit=50, time_range=None):
    """Get echoes by emotion across all users"""
    params = {
        'TableName': 'EchoesTable',
        'IndexName': 'emotion-timestamp-index',
        'KeyConditionExpression': 'emotion = :emotion',
        'ExpressionAttributeValues': {':emotion': emotion},
        'ScanIndexForward': False,
        'Limit': limit
    }
    
    # Add time range filtering if specified
    if time_range:
        params['KeyConditionExpression'] += ' AND #ts BETWEEN :start AND :end'
        params['ExpressionAttributeNames'] = {'#ts': 'timestamp'}
        params['ExpressionAttributeValues'].update({
            ':start': time_range['start'],
            ':end': time_range['end']
        })
    
    return dynamodb.query(**params)

# Optimized version with caching
def get_popular_emotions_cached():
    """Cache popular emotion queries"""
    cache_key = f"popular_emotions_{datetime.now().strftime('%Y%m%d%H')}"
    
    cached_result = redis_client.get(cache_key)
    if cached_result:
        return json.loads(cached_result)
    
    # Query each emotion and cache results
    emotions = ['happy', 'calm', 'excited', 'peaceful', 'energetic']
    results = {}
    
    for emotion in emotions:
        results[emotion] = get_echoes_by_emotion(emotion, limit=10)
    
    redis_client.setex(cache_key, 3600, json.dumps(results))  # 1 hour cache
    return results
```

#### Pattern 4: User's Emotion-Filtered Echoes
**Use Case**: "My calm echoes", personal mood tracking
**Frequency**: Medium (mood-based browsing)
**Performance Target**: < 150ms

```python
def get_user_echoes_by_emotion(user_id, emotion, limit=30):
    """Get user's echoes filtered by emotion"""
    return dynamodb.query(
        TableName='EchoesTable',
        IndexName='userId-emotion-index',
        KeyConditionExpression='userId = :userId AND emotion = :emotion',
        ExpressionAttributeValues={
            ':userId': user_id,
            ':emotion': emotion
        },
        Limit=limit
    )

# Advanced: Emotion analytics for user
def get_user_emotion_summary(user_id, days=30):
    """Get user's emotion distribution over time"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    response = dynamodb.query(
        TableName='EchoesTable',
        KeyConditionExpression='userId = :userId AND #ts BETWEEN :start AND :end',
        ExpressionAttributeNames={'#ts': 'timestamp'},
        ExpressionAttributeValues={
            ':userId': user_id,
            ':start': start_date.isoformat(),
            ':end': end_date.isoformat()
        },
        ProjectionExpression='emotion, #ts',
    )
    
    # Count emotions
    emotion_counts = {}
    for item in response['Items']:
        emotion = item['emotion']
        emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
    
    return emotion_counts
```

### 3. Advanced Query Patterns

#### Pattern 5: Random Echo Selection
**Use Case**: "Play something peaceful", serendipitous discovery
**Frequency**: High (core app feature)
**Performance Target**: < 300ms

```python
def get_random_echo_by_emotion(emotion, user_id=None):
    """Optimized random echo selection"""
    
    # Strategy 1: Use pagination with random offset
    # First, get a count estimate using parallel scans
    segments = 4
    total_items = 0
    
    for segment in range(segments):
        response = dynamodb.scan(
            TableName='EchoesTable',
            IndexName='emotion-timestamp-index',
            FilterExpression='emotion = :emotion',
            ExpressionAttributeValues={':emotion': emotion},
            Select='COUNT',
            Segment=segment,
            TotalSegments=segments
        )
        total_items += response['Count']
    
    if total_items == 0:
        return None
    
    # Get random item using skip logic
    random_offset = random.randint(0, total_items - 1)
    items_skipped = 0
    
    # Query with pagination until we reach the offset
    last_key = None
    while items_skipped < random_offset:
        response = dynamodb.query(
            TableName='EchoesTable',
            IndexName='emotion-timestamp-index',
            KeyConditionExpression='emotion = :emotion',
            ExpressionAttributeValues={':emotion': emotion},
            Limit=min(100, random_offset - items_skipped + 1),
            ExclusiveStartKey=last_key
        )
        
        items_skipped += len(response['Items'])
        last_key = response.get('LastEvaluatedKey')
        
        if not last_key:
            break
    
    # Return the item at our target offset
    target_index = random_offset - (items_skipped - len(response['Items']))
    if target_index < len(response['Items']):
        return response['Items'][target_index]
    
    # Fallback: return random item from last batch
    return random.choice(response['Items']) if response['Items'] else None

# Alternative strategy using time-based sampling
def get_random_echo_by_emotion_time_based(emotion):
    """Time-based random selection (faster but less uniform)"""
    
    # Generate random timestamp in the last year
    now = datetime.now()
    year_ago = now - timedelta(days=365)
    random_time = year_ago + timedelta(
        seconds=random.randint(0, int((now - year_ago).total_seconds()))
    )
    
    # Query from random time point
    response = dynamodb.query(
        TableName='EchoesTable',
        IndexName='emotion-timestamp-index',
        KeyConditionExpression='emotion = :emotion AND #ts >= :timestamp',
        ExpressionAttributeNames={'#ts': 'timestamp'},
        ExpressionAttributeValues={
            ':emotion': emotion,
            ':timestamp': random_time.isoformat()
        },
        Limit=10,
        ScanIndexForward=True
    )
    
    if response['Items']:
        return random.choice(response['Items'])
    
    # Fallback: query backwards from random time
    response = dynamodb.query(
        TableName='EchoesTable',
        IndexName='emotion-timestamp-index',
        KeyConditionExpression='emotion = :emotion AND #ts <= :timestamp',
        ExpressionAttributeNames={'#ts': 'timestamp'},
        ExpressionAttributeValues={
            ':emotion': emotion,
            ':timestamp': random_time.isoformat()
        },
        Limit=10,
        ScanIndexForward=False
    )
    
    return random.choice(response['Items']) if response['Items'] else None
```

#### Pattern 6: Time-Range Queries
**Use Case**: "Echoes from last summer", temporal exploration
**Frequency**: Low (nostalgic browsing)
**Performance Target**: < 500ms

```python
def get_echoes_by_time_range(user_id, start_date, end_date, emotion=None):
    """Get echoes within a time range, optionally filtered by emotion"""
    
    if emotion:
        # Use emotion GSI for cross-user queries
        return dynamodb.query(
            TableName='EchoesTable',
            IndexName='emotion-timestamp-index',
            KeyConditionExpression='emotion = :emotion AND #ts BETWEEN :start AND :end',
            FilterExpression='userId = :userId',  # Additional filter for user
            ExpressionAttributeNames={'#ts': 'timestamp'},
            ExpressionAttributeValues={
                ':emotion': emotion,
                ':start': start_date,
                ':end': end_date,
                ':userId': user_id
            }
        )
    else:
        # Use primary table for user-specific queries
        return dynamodb.query(
            TableName='EchoesTable',
            KeyConditionExpression='userId = :userId AND #ts BETWEEN :start AND :end',
            ExpressionAttributeNames={'#ts': 'timestamp'},
            ExpressionAttributeValues={
                ':userId': user_id,
                ':start': start_date,
                ':end': end_date
            }
        )

# Optimized for common time ranges
def get_echoes_last_week(user_id):
    """Optimized query for recent echoes"""
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    
    return dynamodb.query(
        TableName='EchoesTable',
        KeyConditionExpression='userId = :userId AND #ts >= :weekAgo',
        ExpressionAttributeNames={'#ts': 'timestamp'},
        ExpressionAttributeValues={
            ':userId': user_id,
            ':weekAgo': week_ago
        },
        ScanIndexForward=False
    )
```

## Performance Optimization Strategies

### 1. Caching Layer
```python
import redis
import json
from datetime import datetime, timedelta

class EchoCache:
    def __init__(self):
        self.redis_client = redis.Redis(host='localhost', port=6379, db=0)
        self.default_ttl = 3600  # 1 hour
    
    def get_user_echoes_cached(self, user_id, limit=20):
        """Cache user's recent echoes"""
        cache_key = f"user_echoes:{user_id}:{limit}"
        cached = self.redis_client.get(cache_key)
        
        if cached:
            return json.loads(cached)
        
        # Query database
        result = get_user_echoes(user_id, limit)
        
        # Cache for 30 minutes
        self.redis_client.setex(cache_key, 1800, json.dumps(result))
        return result
    
    def get_emotion_echoes_cached(self, emotion):
        """Cache popular emotion queries"""
        cache_key = f"emotion_echoes:{emotion}:{datetime.now().hour}"
        cached = self.redis_client.get(cache_key)
        
        if cached:
            return json.loads(cached)
        
        result = get_echoes_by_emotion(emotion, limit=100)
        
        # Cache for 1 hour
        self.redis_client.setex(cache_key, 3600, json.dumps(result))
        return result
    
    def invalidate_user_cache(self, user_id):
        """Invalidate user-specific caches when new echo is added"""
        pattern = f"user_echoes:{user_id}:*"
        keys = self.redis_client.keys(pattern)
        if keys:
            self.redis_client.delete(*keys)
```

### 2. Batch Operations
```python
def batch_get_echoes(echo_ids):
    """Efficiently retrieve multiple echoes"""
    
    # Use batch_get_item for multiple echo IDs
    request_items = {
        'EchoesTable': {
            'Keys': [{'echoId': {'S': echo_id}} for echo_id in echo_ids]
        }
    }
    
    response = dynamodb.batch_get_item(RequestItems=request_items)
    return response['Responses']['EchoesTable']

def batch_write_echoes(echoes):
    """Efficiently write multiple echoes"""
    
    with dynamodb.batch_writer() as batch:
        for echo in echoes:
            batch.put_item(Item=echo)
```

### 3. Connection Pooling and Async Operations
```python
import asyncio
import aioboto3

class AsyncEchoService:
    def __init__(self):
        self.session = aioboto3.Session()
    
    async def get_multiple_emotion_echoes(self, emotions):
        """Parallel queries for multiple emotions"""
        
        async with self.session.client('dynamodb') as dynamodb:
            tasks = []
            
            for emotion in emotions:
                task = self.get_echoes_by_emotion_async(dynamodb, emotion)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks)
            
            return dict(zip(emotions, results))
    
    async def get_echoes_by_emotion_async(self, dynamodb, emotion):
        """Async emotion query"""
        response = await dynamodb.query(
            TableName='EchoesTable',
            IndexName='emotion-timestamp-index',
            KeyConditionExpression='emotion = :emotion',
            ExpressionAttributeValues={':emotion': {'S': emotion}},
            Limit=20
        )
        return response['Items']
```

## Query Performance Monitoring

### 1. CloudWatch Metrics
```python
import boto3

def log_query_metrics(query_type, latency_ms, item_count):
    """Log custom metrics to CloudWatch"""
    cloudwatch = boto3.client('cloudwatch')
    
    cloudwatch.put_metric_data(
        Namespace='Echoes/Database',
        MetricData=[
            {
                'MetricName': 'QueryLatency',
                'Dimensions': [
                    {'Name': 'QueryType', 'Value': query_type}
                ],
                'Value': latency_ms,
                'Unit': 'Milliseconds'
            },
            {
                'MetricName': 'ItemsReturned',
                'Dimensions': [
                    {'Name': 'QueryType', 'Value': query_type}
                ],
                'Value': item_count,
                'Unit': 'Count'
            }
        ]
    )

# Usage in query functions
import time

def get_user_echoes_monitored(user_id, limit=20):
    start_time = time.time()
    
    try:
        result = get_user_echoes(user_id, limit)
        latency = (time.time() - start_time) * 1000
        
        log_query_metrics('GetUserEchoes', latency, len(result['Items']))
        return result
        
    except Exception as e:
        latency = (time.time() - start_time) * 1000
        log_query_metrics('GetUserEchoes_Error', latency, 0)
        raise
```

### 2. Query Optimization Rules

1. **Always use KeyConditionExpression over FilterExpression**
2. **Use projection expressions to reduce data transfer**
3. **Implement pagination for large result sets**
4. **Cache frequently accessed data**
5. **Use batch operations for multiple items**
6. **Monitor and optimize GSI usage**
7. **Implement circuit breakers for external dependencies**

### 3. Performance Benchmarks

Target performance metrics for query patterns:
- User echoes (primary): < 100ms
- Direct echo access: < 50ms
- Emotion queries: < 200ms
- Random selection: < 300ms
- Time range queries: < 500ms
- Batch operations: < 1000ms for 25 items

This optimization strategy ensures efficient query performance while supporting millions of echoes across thousands of concurrent users.