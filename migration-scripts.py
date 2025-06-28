#!/usr/bin/env python3
"""
Echoes DynamoDB Migration Scripts
Handles table creation, data migration, and schema updates
"""

import boto3
import json
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import uuid
from decimal import Decimal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EchoesMigration:
    def __init__(self, region: str = 'us-east-1', environment: str = 'dev'):
        self.region = region
        self.environment = environment
        self.table_name = f'EchoesTable-{environment}'
        
        # Initialize AWS clients
        self.dynamodb = boto3.client('dynamodb', region_name=region)
        self.dynamodb_resource = boto3.resource('dynamodb', region_name=region)
        self.s3 = boto3.client('s3', region_name=region)
        
        logger.info(f"Initialized migration for {self.table_name} in {region}")

    def create_table(self, billing_mode: str = 'PAY_PER_REQUEST') -> bool:
        """Create the main EchoesTable with all GSIs"""
        
        try:
            # Define the table schema
            table_definition = {
                'TableName': self.table_name,
                'KeySchema': [
                    {'AttributeName': 'userId', 'KeyType': 'HASH'},
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                ],
                'AttributeDefinitions': [
                    {'AttributeName': 'userId', 'AttributeType': 'S'},
                    {'AttributeName': 'timestamp', 'AttributeType': 'S'},
                    {'AttributeName': 'emotion', 'AttributeType': 'S'},
                    {'AttributeName': 'echoId', 'AttributeType': 'S'}
                ],
                'BillingMode': billing_mode,
                'GlobalSecondaryIndexes': [
                    # GSI 1: Emotion-Timestamp Index
                    {
                        'IndexName': 'emotion-timestamp-index',
                        'KeySchema': [
                            {'AttributeName': 'emotion', 'KeyType': 'HASH'},
                            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'BillingMode': billing_mode
                    },
                    # GSI 2: EchoId Index
                    {
                        'IndexName': 'echoId-index',
                        'KeySchema': [
                            {'AttributeName': 'echoId', 'KeyType': 'HASH'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'BillingMode': billing_mode
                    },
                    # GSI 3: User-Emotion Index
                    {
                        'IndexName': 'userId-emotion-index',
                        'KeySchema': [
                            {'AttributeName': 'userId', 'KeyType': 'HASH'},
                            {'AttributeName': 'emotion', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {
                            'ProjectionType': 'INCLUDE',
                            'NonKeyAttributes': [
                                'timestamp', 'echoId', 's3Url', 'location',
                                'tags', 'detectedMood', 'transcript', 'metadata'
                            ]
                        },
                        'BillingMode': billing_mode
                    }
                ],
                'StreamSpecification': {
                    'StreamEnabled': True,
                    'StreamViewType': 'NEW_AND_OLD_IMAGES'
                },
                'SSESpecification': {
                    'Enabled': True
                },
                'Tags': [
                    {'Key': 'Environment', 'Value': self.environment},
                    {'Key': 'Application', 'Value': 'Echoes'},
                    {'Key': 'Component', 'Value': 'Database'}
                ]
            }
            
            # Add provisioned capacity if needed
            if billing_mode == 'PROVISIONED':
                provisioned_throughput = {
                    'ReadCapacityUnits': 100,
                    'WriteCapacityUnits': 100
                }
                table_definition['ProvisionedThroughput'] = provisioned_throughput
                
                # Add to GSIs
                for gsi in table_definition['GlobalSecondaryIndexes']:
                    gsi['ProvisionedThroughput'] = provisioned_throughput.copy()
            
            # Create the table
            response = self.dynamodb.create_table(**table_definition)
            logger.info(f"Table creation initiated: {response['TableDescription']['TableName']}")
            
            # Wait for table to be active
            waiter = self.dynamodb.get_waiter('table_exists')
            logger.info("Waiting for table to become active...")
            waiter.wait(TableName=self.table_name)
            
            # Enable TTL
            self.enable_ttl()
            
            logger.info(f"Table {self.table_name} created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error creating table: {e}")
            return False

    def enable_ttl(self) -> bool:
        """Enable TTL on the ttl attribute"""
        try:
            self.dynamodb.update_time_to_live(
                TableName=self.table_name,
                TimeToLiveSpecification={
                    'AttributeName': 'ttl',
                    'Enabled': True
                }
            )
            logger.info("TTL enabled successfully")
            return True
        except Exception as e:
            logger.error(f"Error enabling TTL: {e}")
            return False

    def wait_for_table_ready(self) -> bool:
        """Wait for table and all GSIs to be active"""
        try:
            # Wait for table
            waiter = self.dynamodb.get_waiter('table_exists')
            waiter.wait(TableName=self.table_name)
            
            # Check GSI status
            while True:
                response = self.dynamodb.describe_table(TableName=self.table_name)
                table_status = response['Table']['TableStatus']
                
                if table_status != 'ACTIVE':
                    logger.info(f"Table status: {table_status}")
                    time.sleep(10)
                    continue
                
                # Check GSI status
                gsi_statuses = []
                if 'GlobalSecondaryIndexes' in response['Table']:
                    for gsi in response['Table']['GlobalSecondaryIndexes']:
                        gsi_statuses.append(gsi['IndexStatus'])
                
                if all(status == 'ACTIVE' for status in gsi_statuses):
                    logger.info("Table and all GSIs are active")
                    return True
                else:
                    logger.info(f"GSI statuses: {gsi_statuses}")
                    time.sleep(10)
                    
        except Exception as e:
            logger.error(f"Error waiting for table: {e}")
            return False

    def migrate_sample_data(self, num_users: int = 10, echoes_per_user: int = 50) -> bool:
        """Generate and insert sample data for testing"""
        
        try:
            table = self.dynamodb_resource.Table(self.table_name)
            emotions = ['happy', 'calm', 'excited', 'peaceful', 'energetic', 'nostalgic', 'contemplative']
            tags_options = [
                ['nature', 'outdoor'], ['music', 'concert'], ['family', 'home'],
                ['work', 'meeting'], ['exercise', 'gym'], ['food', 'restaurant'],
                ['travel', 'vacation'], ['friends', 'social'], ['reading', 'quiet']
            ]
            
            total_items = num_users * echoes_per_user
            logger.info(f"Generating {total_items} sample echoes...")
            
            with table.batch_writer() as batch:
                for user_idx in range(num_users):
                    user_id = f"user_{user_idx:04d}"
                    
                    for echo_idx in range(echoes_per_user):
                        # Generate timestamp (last 365 days)
                        days_ago = echo_idx * (365 / echoes_per_user)
                        timestamp = (datetime.now() - timedelta(days=days_ago)).isoformat()
                        
                        # Generate echo data
                        emotion = emotions[echo_idx % len(emotions)]
                        echo_id = f"echo_{uuid.uuid4().hex[:16]}"
                        tags = tags_options[echo_idx % len(tags_options)]
                        
                        item = {
                            'userId': user_id,
                            'timestamp': timestamp,
                            'echoId': echo_id,
                            'emotion': emotion,
                            's3Url': f"s3://echoes-audio-{self.environment}/{user_id}/{echo_id}.webm",
                            'location': {
                                'lat': Decimal(str(37.7749 + (user_idx - 5) * 0.1)),
                                'lng': Decimal(str(-122.4194 + (echo_idx - 25) * 0.1))
                            },
                            'tags': tags,
                            'transcript': f"Sample transcript for {emotion} echo {echo_idx}",
                            'detectedMood': emotion,
                            'createdAt': timestamp,
                            'updatedAt': timestamp,
                            'version': 1,
                            'metadata': {
                                'duration': Decimal(str(15 + (echo_idx % 20))),
                                'fileSize': 1048576 + (echo_idx * 10000),
                                'audioFormat': 'webm',
                                'transcriptionConfidence': Decimal('0.95')
                            }
                        }
                        
                        batch.put_item(Item=item)
                        
                        if (user_idx * echoes_per_user + echo_idx + 1) % 100 == 0:
                            logger.info(f"Inserted {user_idx * echoes_per_user + echo_idx + 1} items")
            
            logger.info(f"Successfully inserted {total_items} sample echoes")
            return True
            
        except Exception as e:
            logger.error(f"Error migrating sample data: {e}")
            return False

    def migrate_from_backup(self, backup_bucket: str, backup_key: str) -> bool:
        """Migrate data from S3 backup"""
        
        try:
            # Download backup file
            logger.info(f"Downloading backup from s3://{backup_bucket}/{backup_key}")
            response = self.s3.get_object(Bucket=backup_bucket, Key=backup_key)
            backup_data = json.loads(response['Body'].read())
            
            table = self.dynamodb_resource.Table(self.table_name)
            
            # Process in batches
            batch_size = 25
            total_items = len(backup_data)
            
            logger.info(f"Migrating {total_items} items from backup")
            
            for i in range(0, total_items, batch_size):
                batch = backup_data[i:i + batch_size]
                
                with table.batch_writer() as writer:
                    for item in batch:
                        # Convert any float values to Decimal for DynamoDB
                        item = self._convert_floats_to_decimal(item)
                        writer.put_item(Item=item)
                
                logger.info(f"Migrated {min(i + batch_size, total_items)} / {total_items} items")
                time.sleep(0.1)  # Rate limiting
            
            logger.info("Backup migration completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error migrating from backup: {e}")
            return False

    def _convert_floats_to_decimal(self, obj: Any) -> Any:
        """Convert float values to Decimal for DynamoDB compatibility"""
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {k: self._convert_floats_to_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_floats_to_decimal(v) for v in obj]
        else:
            return obj

    def backup_table_to_s3(self, backup_bucket: str, backup_prefix: str = None) -> bool:
        """Backup table data to S3"""
        
        try:
            if backup_prefix is None:
                backup_prefix = f"backups/{self.table_name}/{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            table = self.dynamodb_resource.Table(self.table_name)
            
            # Scan all items
            logger.info("Scanning table for backup...")
            items = []
            
            scan_kwargs = {}
            while True:
                response = table.scan(**scan_kwargs)
                items.extend(response['Items'])
                
                if 'LastEvaluatedKey' not in response:
                    break
                    
                scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
                logger.info(f"Scanned {len(items)} items so far...")
            
            # Convert Decimal to float for JSON serialization
            serializable_items = []
            for item in items:
                serializable_items.append(self._convert_decimal_to_float(item))
            
            # Upload to S3
            backup_key = f"{backup_prefix}/data.json"
            logger.info(f"Uploading backup to s3://{backup_bucket}/{backup_key}")
            
            self.s3.put_object(
                Bucket=backup_bucket,
                Key=backup_key,
                Body=json.dumps(serializable_items, indent=2),
                ContentType='application/json'
            )
            
            logger.info(f"Backed up {len(items)} items to S3")
            return True
            
        except Exception as e:
            logger.error(f"Error backing up table: {e}")
            return False

    def _convert_decimal_to_float(self, obj: Any) -> Any:
        """Convert Decimal values to float for JSON serialization"""
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: self._convert_decimal_to_float(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_decimal_to_float(v) for v in obj]
        else:
            return obj

    def validate_migration(self) -> bool:
        """Validate the migration by running test queries"""
        
        try:
            table = self.dynamodb_resource.Table(self.table_name)
            
            # Test 1: Primary table scan
            logger.info("Testing primary table access...")
            response = table.scan(Limit=5)
            if not response['Items']:
                logger.warning("No items found in primary table")
                return False
            
            sample_item = response['Items'][0]
            logger.info(f"Sample item: {sample_item['userId']}")
            
            # Test 2: GSI queries
            logger.info("Testing GSI queries...")
            
            # Test emotion-timestamp-index
            response = table.query(
                IndexName='emotion-timestamp-index',
                KeyConditionExpression='emotion = :emotion',
                ExpressionAttributeValues={':emotion': sample_item['emotion']},
                Limit=1
            )
            if not response['Items']:
                logger.error("emotion-timestamp-index query failed")
                return False
            
            # Test echoId-index
            response = table.query(
                IndexName='echoId-index',
                KeyConditionExpression='echoId = :echoId',
                ExpressionAttributeValues={':echoId': sample_item['echoId']},
                Limit=1
            )
            if not response['Items']:
                logger.error("echoId-index query failed")
                return False
            
            # Test userId-emotion-index
            response = table.query(
                IndexName='userId-emotion-index',
                KeyConditionExpression='userId = :userId AND emotion = :emotion',
                ExpressionAttributeValues={
                    ':userId': sample_item['userId'],
                    ':emotion': sample_item['emotion']
                },
                Limit=1
            )
            if not response['Items']:
                logger.error("userId-emotion-index query failed")
                return False
            
            logger.info("All validation tests passed")
            return True
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return False

    def delete_table(self, confirm: bool = False) -> bool:
        """Delete the table (with confirmation)"""
        
        if not confirm:
            logger.warning("Table deletion not confirmed. Use confirm=True to proceed.")
            return False
        
        try:
            self.dynamodb.delete_table(TableName=self.table_name)
            logger.info(f"Table {self.table_name} deletion initiated")
            
            # Wait for deletion
            waiter = self.dynamodb.get_waiter('table_not_exists')
            waiter.wait(TableName=self.table_name)
            
            logger.info(f"Table {self.table_name} deleted successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting table: {e}")
            return False


def main():
    """Main migration function with CLI interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Echoes DynamoDB Migration Tool')
    parser.add_argument('--environment', default='dev', choices=['dev', 'staging', 'prod'])
    parser.add_argument('--region', default='us-east-1')
    parser.add_argument('--action', required=True, choices=[
        'create', 'migrate-sample', 'migrate-backup', 'backup', 'validate', 'delete'
    ])
    parser.add_argument('--billing-mode', default='PAY_PER_REQUEST', choices=['PAY_PER_REQUEST', 'PROVISIONED'])
    parser.add_argument('--backup-bucket', help='S3 bucket for backup operations')
    parser.add_argument('--backup-key', help='S3 key for backup file')
    parser.add_argument('--num-users', type=int, default=10, help='Number of users for sample data')
    parser.add_argument('--echoes-per-user', type=int, default=50, help='Echoes per user for sample data')
    parser.add_argument('--confirm', action='store_true', help='Confirm destructive operations')
    
    args = parser.parse_args()
    
    # Initialize migration
    migration = EchoesMigration(region=args.region, environment=args.environment)
    
    # Execute action
    success = False
    
    if args.action == 'create':
        success = migration.create_table(billing_mode=args.billing_mode)
        if success:
            success = migration.wait_for_table_ready()
    
    elif args.action == 'migrate-sample':
        success = migration.migrate_sample_data(args.num_users, args.echoes_per_user)
    
    elif args.action == 'migrate-backup':
        if not args.backup_bucket or not args.backup_key:
            logger.error("--backup-bucket and --backup-key required for backup migration")
            return False
        success = migration.migrate_from_backup(args.backup_bucket, args.backup_key)
    
    elif args.action == 'backup':
        if not args.backup_bucket:
            logger.error("--backup-bucket required for backup operation")
            return False
        success = migration.backup_table_to_s3(args.backup_bucket)
    
    elif args.action == 'validate':
        success = migration.validate_migration()
    
    elif args.action == 'delete':
        success = migration.delete_table(confirm=args.confirm)
    
    if success:
        logger.info(f"Action '{args.action}' completed successfully")
        return True
    else:
        logger.error(f"Action '{args.action}' failed")
        return False


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)