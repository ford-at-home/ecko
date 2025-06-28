#!/usr/bin/env python3
"""
Echoes Migration Runner - Orchestrates database setup and data seeding
"""

import sys
import os
import logging
import argparse
import json
from datetime import datetime
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Import our migration and seeding modules
from migrations.migration_manager import MigrationManager
from seeds import EchoesSeeder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MigrationRunner:
    """Orchestrates the complete database setup process"""
    
    def __init__(self, region: str = 'us-east-1', environment: str = 'dev'):
        self.region = region
        self.environment = environment
        
        # Initialize components
        self.migration_manager = MigrationManager(region, environment)
        self.seeder = EchoesSeeder(region, environment)
        
        logger.info(f"Migration runner initialized for {environment} environment")
    
    def setup_database(self, seed_demo: bool = True, seed_test: bool = False) -> bool:
        """Complete database setup: migrations + seeding"""
        
        try:
            logger.info("Starting complete database setup...")
            
            # Step 1: Run migrations
            logger.info("=== Running Database Migrations ===")
            if not self.migration_manager.migrate_up():
                logger.error("Migration failed, aborting setup")
                return False
            
            # Step 2: Seed demo data if requested
            if seed_demo:
                logger.info("=== Seeding Demo Data ===")
                if not self.seeder.seed_demo_data():
                    logger.error("Demo data seeding failed")
                    return False
            
            # Step 3: Seed test scenarios if requested
            if seed_test:
                logger.info("=== Seeding Test Scenarios ===")
                if not self.seeder.seed_test_scenarios():
                    logger.error("Test scenario seeding failed")
                    return False
            
            # Step 4: Validate setup
            logger.info("=== Validating Database Setup ===")
            if not self.validate_complete_setup():
                logger.error("Database validation failed")
                return False
            
            logger.info("Database setup completed successfully!")
            self.print_setup_summary()
            
            return True
            
        except Exception as e:
            logger.error(f"Error during database setup: {e}")
            return False
    
    def validate_complete_setup(self) -> bool:
        """Validate that the complete setup is working correctly"""
        
        try:
            import boto3
            
            # Test DynamoDB connection and basic operations
            dynamodb = boto3.resource('dynamodb', region_name=self.region)
            table_name = f'EchoesTable-{self.environment}'
            table = dynamodb.Table(table_name)
            
            # Test 1: Table exists and is active
            table_info = table.table_status
            if table_info != 'ACTIVE':
                logger.error(f"Table {table_name} is not active: {table_info}")
                return False
            
            # Test 2: Can read data
            response = table.scan(Limit=1)
            if 'Items' not in response:
                logger.error("Could not read from table")
                return False
            
            # Test 3: Test GSI queries
            if response['Items']:
                sample_item = response['Items'][0]
                
                # Test emotion-timestamp-index
                emotion_response = table.query(
                    IndexName='emotion-timestamp-index',
                    KeyConditionExpression='emotion = :emotion',
                    ExpressionAttributeValues={':emotion': sample_item['emotion']},
                    Limit=1
                )
                
                if not emotion_response['Items']:
                    logger.error("emotion-timestamp-index query failed")
                    return False
                
                # Test echoId-index
                echo_response = table.query(
                    IndexName='echoId-index',
                    KeyConditionExpression='echoId = :echoId',
                    ExpressionAttributeValues={':echoId': sample_item['echoId']},
                    Limit=1
                )
                
                if not echo_response['Items']:
                    logger.error("echoId-index query failed")
                    return False
            
            logger.info("Database validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return False
    
    def print_setup_summary(self):
        """Print a summary of the setup"""
        
        try:
            # Get migration status
            migration_status = self.migration_manager.get_migration_status()
            
            # Get table info
            import boto3
            dynamodb = boto3.client('dynamodb', region_name=self.region)
            table_name = f'EchoesTable-{self.environment}'
            
            table_info = dynamodb.describe_table(TableName=table_name)
            item_count = table_info['Table'].get('ItemCount', 'Unknown')
            
            print("\n" + "="*60)
            print("DATABASE SETUP SUMMARY")
            print("="*60)
            print(f"Environment: {self.environment}")
            print(f"Region: {self.region}")
            print(f"Table: {table_name}")
            print(f"Status: {table_info['Table']['TableStatus']}")
            print(f"Item Count: {item_count}")
            print(f"Applied Migrations: {migration_status.get('applied_count', 0)}")
            print(f"Pending Migrations: {migration_status.get('pending_count', 0)}")
            
            # GSI information
            if 'GlobalSecondaryIndexes' in table_info['Table']:
                print(f"Global Secondary Indexes: {len(table_info['Table']['GlobalSecondaryIndexes'])}")
                for gsi in table_info['Table']['GlobalSecondaryIndexes']:
                    print(f"  - {gsi['IndexName']}: {gsi['IndexStatus']}")
            
            print("\nCONNECTION DETAILS:")
            print(f"AWS Region: {self.region}")
            print(f"Table Name: {table_name}")
            print(f"Migration Table: EchoesMigrations-{self.environment}")
            
            print("\nNEXT STEPS:")
            print("1. Test the API endpoints with the demo data")
            print("2. Run integration tests")
            print("3. Configure your application to use this database")
            print("="*60)
            
        except Exception as e:
            logger.warning(f"Could not generate summary: {e}")
    
    def reset_database(self, confirm: bool = False) -> bool:
        """Reset the entire database (destructive operation)"""
        
        if not confirm:
            logger.warning("Database reset not confirmed. Use --confirm to proceed.")
            return False
        
        try:
            logger.warning("DESTRUCTIVE OPERATION: Resetting entire database")
            
            # Step 1: Clear all data
            logger.info("=== Clearing All Data ===")
            if not self.seeder.clear_demo_data(confirm=True):
                logger.error("Failed to clear demo data")
                return False
            
            # Step 2: Rollback all migrations
            logger.info("=== Rolling Back Migrations ===")
            if not self.migration_manager.migrate_down('0'):
                logger.error("Failed to rollback migrations")
                return False
            
            logger.info("Database reset completed")
            return True
            
        except Exception as e:
            logger.error(f"Error during database reset: {e}")
            return False
    
    def backup_database(self, backup_bucket: str) -> bool:
        """Create a backup of the current database"""
        
        try:
            logger.info(f"Creating database backup to s3://{backup_bucket}")
            
            # Use the existing backup functionality from the original migration script
            from migration_scripts import EchoesMigration
            
            migration = EchoesMigration(self.region, self.environment)
            success = migration.backup_table_to_s3(backup_bucket)
            
            if success:
                logger.info("Database backup completed successfully")
            else:
                logger.error("Database backup failed")
            
            return success
            
        except Exception as e:
            logger.error(f"Error during backup: {e}")
            return False
    
    def restore_from_backup(self, backup_bucket: str, backup_key: str) -> bool:
        """Restore database from backup"""
        
        try:
            logger.info(f"Restoring database from s3://{backup_bucket}/{backup_key}")
            
            # Use the existing restore functionality
            from migration_scripts import EchoesMigration
            
            migration = EchoesMigration(self.region, self.environment)
            success = migration.migrate_from_backup(backup_bucket, backup_key)
            
            if success:
                logger.info("Database restoration completed successfully")
            else:
                logger.error("Database restoration failed")
            
            return success
            
        except Exception as e:
            logger.error(f"Error during restoration: {e}")
            return False


def main():
    """Main CLI interface"""
    
    parser = argparse.ArgumentParser(
        description='Echoes Database Migration Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Complete setup for development
  python migrate.py setup --environment dev

  # Setup without demo data
  python migrate.py setup --no-demo

  # Run only migrations
  python migrate.py migrate

  # Seed only demo data
  python migrate.py seed

  # Check migration status
  python migrate.py status

  # Reset everything (careful!)
  python migrate.py reset --confirm

  # Create backup
  python migrate.py backup --bucket my-backup-bucket

  # Restore from backup
  python migrate.py restore --bucket my-backup-bucket --key backups/data.json
        """
    )
    
    parser.add_argument('command', choices=[
        'setup', 'migrate', 'seed', 'status', 'reset', 'backup', 'restore'
    ], help='Command to execute')
    
    parser.add_argument('--environment', default='dev', 
                       choices=['dev', 'staging', 'prod'],
                       help='Environment to operate on')
    
    parser.add_argument('--region', default='us-east-1',
                       help='AWS region')
    
    parser.add_argument('--no-demo', action='store_true',
                       help='Skip demo data seeding')
    
    parser.add_argument('--with-test', action='store_true',
                       help='Include test scenario seeding')
    
    parser.add_argument('--confirm', action='store_true',
                       help='Confirm destructive operations')
    
    parser.add_argument('--bucket', help='S3 bucket for backup operations')
    parser.add_argument('--key', help='S3 key for restore operations')
    
    args = parser.parse_args()
    
    # Initialize runner
    runner = MigrationRunner(region=args.region, environment=args.environment)
    
    # Execute command
    success = False
    
    if args.command == 'setup':
        success = runner.setup_database(
            seed_demo=not args.no_demo,
            seed_test=args.with_test
        )
    
    elif args.command == 'migrate':
        success = runner.migration_manager.migrate_up()
    
    elif args.command == 'seed':
        success = runner.seeder.seed_demo_data()
        if success and args.with_test:
            success = runner.seeder.seed_test_scenarios()
    
    elif args.command == 'status':
        status = runner.migration_manager.get_migration_status()
        print(json.dumps(status, indent=2))
        success = True
    
    elif args.command == 'reset':
        success = runner.reset_database(confirm=args.confirm)
    
    elif args.command == 'backup':
        if not args.bucket:
            logger.error("--bucket required for backup command")
            return False
        success = runner.backup_database(args.bucket)
    
    elif args.command == 'restore':
        if not args.bucket or not args.key:
            logger.error("--bucket and --key required for restore command")
            return False
        success = runner.restore_from_backup(args.bucket, args.key)
    
    if success:
        logger.info(f"Command '{args.command}' completed successfully")
        return True
    else:
        logger.error(f"Command '{args.command}' failed")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)