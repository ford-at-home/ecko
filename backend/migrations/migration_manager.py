#!/usr/bin/env python3
"""
Migration Manager - Handles database migration versioning and execution
"""

import boto3
import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from abc import ABC, abstractmethod
import importlib.util
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Migration(ABC):
    """Abstract base class for database migrations"""
    
    def __init__(self, version: str, description: str):
        self.version = version
        self.description = description
        self.timestamp = datetime.now().isoformat()
    
    @abstractmethod
    def up(self, dynamodb_client, dynamodb_resource) -> bool:
        """Apply the migration"""
        pass
    
    @abstractmethod
    def down(self, dynamodb_client, dynamodb_resource) -> bool:
        """Rollback the migration"""
        pass


class MigrationManager:
    """Manages database migrations with version tracking"""
    
    def __init__(self, region: str = 'us-east-1', environment: str = 'dev'):
        self.region = region
        self.environment = environment
        self.migration_table = f'EchoesMigrations-{environment}'
        self.main_table = f'EchoesTable-{environment}'
        
        # Initialize AWS clients
        self.dynamodb = boto3.client('dynamodb', region_name=region)
        self.dynamodb_resource = boto3.resource('dynamodb', region_name=region)
        
        # Migration directory
        self.migrations_dir = Path(__file__).parent / 'versions'
        self.migrations_dir.mkdir(exist_ok=True)
        
        logger.info(f"Migration manager initialized for {environment} environment")
    
    def create_migration_table(self) -> bool:
        """Create the migration tracking table"""
        try:
            table_definition = {
                'TableName': self.migration_table,
                'KeySchema': [
                    {'AttributeName': 'version', 'KeyType': 'HASH'}
                ],
                'AttributeDefinitions': [
                    {'AttributeName': 'version', 'AttributeType': 'S'}
                ],
                'BillingMode': 'PAY_PER_REQUEST',
                'Tags': [
                    {'Key': 'Environment', 'Value': self.environment},
                    {'Key': 'Application', 'Value': 'Echoes'},
                    {'Key': 'Component', 'Value': 'Migrations'}
                ]
            }
            
            self.dynamodb.create_table(**table_definition)
            logger.info(f"Migration table {self.migration_table} created")
            
            # Wait for table to be active
            waiter = self.dynamodb.get_waiter('table_exists')
            waiter.wait(TableName=self.migration_table)
            
            return True
            
        except self.dynamodb.exceptions.ResourceInUseException:
            logger.info(f"Migration table {self.migration_table} already exists")
            return True
        except Exception as e:
            logger.error(f"Error creating migration table: {e}")
            return False
    
    def get_applied_migrations(self) -> List[str]:
        """Get list of applied migration versions"""
        try:
            table = self.dynamodb_resource.Table(self.migration_table)
            response = table.scan()
            
            versions = [item['version'] for item in response['Items']]
            return sorted(versions)
            
        except Exception as e:
            logger.error(f"Error getting applied migrations: {e}")
            return []
    
    def record_migration(self, migration: Migration, status: str = 'applied') -> bool:
        """Record a migration in the tracking table"""
        try:
            table = self.dynamodb_resource.Table(self.migration_table)
            
            item = {
                'version': migration.version,
                'description': migration.description,
                'applied_at': datetime.now().isoformat(),
                'status': status,
                'environment': self.environment
            }
            
            table.put_item(Item=item)
            logger.info(f"Migration {migration.version} recorded as {status}")
            return True
            
        except Exception as e:
            logger.error(f"Error recording migration: {e}")
            return False
    
    def remove_migration_record(self, version: str) -> bool:
        """Remove a migration record (for rollbacks)"""
        try:
            table = self.dynamodb_resource.Table(self.migration_table)
            table.delete_item(Key={'version': version})
            logger.info(f"Migration record {version} removed")
            return True
            
        except Exception as e:
            logger.error(f"Error removing migration record: {e}")
            return False
    
    def load_migration_files(self) -> List[Migration]:
        """Load all migration files from the versions directory"""
        migrations = []
        
        for file_path in sorted(self.migrations_dir.glob('*.py')):
            if file_path.name.startswith('__'):
                continue
                
            try:
                # Load module
                spec = importlib.util.spec_from_file_location(
                    file_path.stem, file_path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Get migration class
                if hasattr(module, 'migration'):
                    migrations.append(module.migration)
                    logger.debug(f"Loaded migration: {module.migration.version}")
                
            except Exception as e:
                logger.error(f"Error loading migration {file_path}: {e}")
                continue
        
        return sorted(migrations, key=lambda m: m.version)
    
    def get_pending_migrations(self) -> List[Migration]:
        """Get migrations that haven't been applied yet"""
        applied_versions = set(self.get_applied_migrations())
        all_migrations = self.load_migration_files()
        
        pending = [m for m in all_migrations if m.version not in applied_versions]
        return pending
    
    def migrate_up(self, target_version: Optional[str] = None) -> bool:
        """Apply pending migrations up to target version"""
        try:
            # Ensure migration table exists
            if not self.create_migration_table():
                return False
            
            pending = self.get_pending_migrations()
            
            if not pending:
                logger.info("No pending migrations to apply")
                return True
            
            # Filter to target version if specified
            if target_version:
                pending = [m for m in pending if m.version <= target_version]
            
            logger.info(f"Applying {len(pending)} migrations...")
            
            for migration in pending:
                logger.info(f"Applying migration {migration.version}: {migration.description}")
                
                try:
                    # Apply migration
                    success = migration.up(self.dynamodb, self.dynamodb_resource)
                    
                    if success:
                        # Record successful migration
                        self.record_migration(migration, 'applied')
                        logger.info(f"Migration {migration.version} applied successfully")
                    else:
                        logger.error(f"Migration {migration.version} failed")
                        return False
                        
                except Exception as e:
                    logger.error(f"Error applying migration {migration.version}: {e}")
                    return False
            
            logger.info("All migrations applied successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error during migration: {e}")
            return False
    
    def migrate_down(self, target_version: str) -> bool:
        """Rollback migrations down to target version"""
        try:
            applied_versions = self.get_applied_migrations()
            all_migrations = self.load_migration_files()
            
            # Find migrations to rollback (in reverse order)
            to_rollback = []
            for migration in reversed(all_migrations):
                if migration.version in applied_versions and migration.version > target_version:
                    to_rollback.append(migration)
            
            if not to_rollback:
                logger.info("No migrations to rollback")
                return True
            
            logger.info(f"Rolling back {len(to_rollback)} migrations...")
            
            for migration in to_rollback:
                logger.info(f"Rolling back migration {migration.version}: {migration.description}")
                
                try:
                    # Rollback migration
                    success = migration.down(self.dynamodb, self.dynamodb_resource)
                    
                    if success:
                        # Remove migration record
                        self.remove_migration_record(migration.version)
                        logger.info(f"Migration {migration.version} rolled back successfully")
                    else:
                        logger.error(f"Migration {migration.version} rollback failed")
                        return False
                        
                except Exception as e:
                    logger.error(f"Error rolling back migration {migration.version}: {e}")
                    return False
            
            logger.info("All migrations rolled back successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error during rollback: {e}")
            return False
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Get current migration status"""
        try:
            applied = self.get_applied_migrations()
            all_migrations = self.load_migration_files()
            pending = self.get_pending_migrations()
            
            status = {
                'environment': self.environment,
                'applied_count': len(applied),
                'pending_count': len(pending),
                'total_migrations': len(all_migrations),
                'applied_versions': applied,
                'pending_versions': [m.version for m in pending],
                'last_applied': applied[-1] if applied else None
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting migration status: {e}")
            return {}
    
    def create_migration_file(self, description: str) -> str:
        """Create a new migration file template"""
        try:
            # Generate version (timestamp-based)
            version = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{version}_{description.lower().replace(' ', '_')}.py"
            filepath = self.migrations_dir / filename
            
            template = f'''"""
Migration {version}: {description}
"""

from migrations.migration_manager import Migration


class {description.replace(' ', '')}Migration(Migration):
    def __init__(self):
        super().__init__(
            version="{version}",
            description="{description}"
        )
    
    def up(self, dynamodb_client, dynamodb_resource) -> bool:
        """Apply the migration"""
        try:
            # TODO: Implement migration logic
            # Example:
            # table = dynamodb_resource.Table('your-table-name')
            # ... perform changes ...
            
            return True
            
        except Exception as e:
            print(f"Error in migration up: {{e}}")
            return False
    
    def down(self, dynamodb_client, dynamodb_resource) -> bool:
        """Rollback the migration"""
        try:
            # TODO: Implement rollback logic
            # Example:
            # table = dynamodb_resource.Table('your-table-name')
            # ... revert changes ...
            
            return True
            
        except Exception as e:
            print(f"Error in migration down: {{e}}")
            return False


# Create migration instance
migration = {description.replace(' ', '')}Migration()
'''
            
            with open(filepath, 'w') as f:
                f.write(template)
            
            logger.info(f"Migration file created: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Error creating migration file: {e}")
            return ""


def main():
    """Main CLI interface for migration management"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Echoes Migration Manager')
    parser.add_argument('--environment', default='dev', choices=['dev', 'staging', 'prod'])
    parser.add_argument('--region', default='us-east-1')
    parser.add_argument('command', choices=['up', 'down', 'status', 'create'])
    parser.add_argument('--target-version', help='Target version for up/down commands')
    parser.add_argument('--description', help='Description for new migration')
    
    args = parser.parse_args()
    
    manager = MigrationManager(region=args.region, environment=args.environment)
    
    if args.command == 'up':
        success = manager.migrate_up(args.target_version)
    elif args.command == 'down':
        if not args.target_version:
            logger.error("Target version required for down command")
            return False
        success = manager.migrate_down(args.target_version)
    elif args.command == 'status':
        status = manager.get_migration_status()
        print(json.dumps(status, indent=2))
        return True
    elif args.command == 'create':
        if not args.description:
            logger.error("Description required for create command")
            return False
        filepath = manager.create_migration_file(args.description)
        return bool(filepath)
    
    return success


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)