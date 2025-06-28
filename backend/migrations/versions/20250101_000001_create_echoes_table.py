"""
Migration 20250101_000001: Create Echoes Table
"""

import time
import logging
from migrations.migration_manager import Migration

logger = logging.getLogger(__name__)


class CreateEchoesTableMigration(Migration):
    def __init__(self):
        super().__init__(
            version="20250101_000001",
            description="Create Echoes Table with GSIs"
        )
    
    def up(self, dynamodb_client, dynamodb_resource) -> bool:
        """Create the main EchoesTable with all GSIs"""
        try:
            table_name = f'EchoesTable-dev'  # Will be parameterized in production
            
            # Check if table already exists (idempotent)
            try:
                dynamodb_client.describe_table(TableName=table_name)
                logger.info(f"Table {table_name} already exists, skipping creation")
                return True
            except dynamodb_client.exceptions.ResourceNotFoundException:
                pass  # Table doesn't exist, proceed with creation
            
            # Define the table schema
            table_definition = {
                'TableName': table_name,
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
                'BillingMode': 'PAY_PER_REQUEST',
                'GlobalSecondaryIndexes': [
                    # GSI 1: Emotion-Timestamp Index
                    {
                        'IndexName': 'emotion-timestamp-index',
                        'KeySchema': [
                            {'AttributeName': 'emotion', 'KeyType': 'HASH'},
                            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'BillingMode': 'PAY_PER_REQUEST'
                    },
                    # GSI 2: EchoId Index
                    {
                        'IndexName': 'echoId-index',
                        'KeySchema': [
                            {'AttributeName': 'echoId', 'KeyType': 'HASH'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'BillingMode': 'PAY_PER_REQUEST'
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
                        'BillingMode': 'PAY_PER_REQUEST'
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
                    {'Key': 'Environment', 'Value': 'dev'},
                    {'Key': 'Application', 'Value': 'Echoes'},
                    {'Key': 'Component', 'Value': 'Database'}
                ]
            }
            
            # Create the table
            response = dynamodb_client.create_table(**table_definition)
            logger.info(f"Table creation initiated: {response['TableDescription']['TableName']}")
            
            # Wait for table to be active
            waiter = dynamodb_client.get_waiter('table_exists')
            logger.info("Waiting for table to become active...")
            waiter.wait(TableName=table_name)
            
            # Wait for all GSIs to be active
            self._wait_for_gsis_active(dynamodb_client, table_name)
            
            # Enable TTL
            try:
                dynamodb_client.update_time_to_live(
                    TableName=table_name,
                    TimeToLiveSpecification={
                        'AttributeName': 'ttl',
                        'Enabled': True
                    }
                )
                logger.info("TTL enabled successfully")
            except Exception as e:
                logger.warning(f"Could not enable TTL: {e}")
            
            logger.info(f"Table {table_name} created successfully with all GSIs")
            return True
            
        except Exception as e:
            logger.error(f"Error creating table: {e}")
            return False
    
    def down(self, dynamodb_client, dynamodb_resource) -> bool:
        """Delete the EchoesTable"""
        try:
            table_name = f'EchoesTable-dev'
            
            # Check if table exists
            try:
                dynamodb_client.describe_table(TableName=table_name)
            except dynamodb_client.exceptions.ResourceNotFoundException:
                logger.info(f"Table {table_name} doesn't exist, nothing to rollback")
                return True
            
            # Delete the table
            dynamodb_client.delete_table(TableName=table_name)
            logger.info(f"Table {table_name} deletion initiated")
            
            # Wait for deletion
            waiter = dynamodb_client.get_waiter('table_not_exists')
            waiter.wait(TableName=table_name)
            
            logger.info(f"Table {table_name} deleted successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting table: {e}")
            return False
    
    def _wait_for_gsis_active(self, dynamodb_client, table_name):
        """Wait for all GSIs to be active"""
        while True:
            response = dynamodb_client.describe_table(TableName=table_name)
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
                break
            else:
                logger.info(f"GSI statuses: {gsi_statuses}")
                time.sleep(10)


# Create migration instance
migration = CreateEchoesTableMigration()