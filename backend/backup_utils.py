#!/usr/bin/env python3
"""
Echoes Database Backup Utilities - Comprehensive backup and restore functionality
"""

import boto3
import json
import gzip
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
import argparse
import sys
from pathlib import Path
import hashlib
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BackupManager:
    """Comprehensive backup and restore manager for Echoes DynamoDB data"""
    
    def __init__(self, region: str = 'us-east-1', environment: str = 'dev'):
        self.region = region
        self.environment = environment
        self.table_name = f'EchoesTable-{environment}'
        self.migration_table = f'EchoesMigrations-{environment}'
        
        # Initialize AWS clients
        self.dynamodb = boto3.client('dynamodb', region_name=region)
        self.dynamodb_resource = boto3.resource('dynamodb', region_name=region)
        self.s3 = boto3.client('s3', region_name=region)
        
        # Backup configuration
        self.backup_config = {
            'compression': True,
            'include_metadata': True,
            'batch_size': 100,
            'max_workers': 4,
            'chunk_size': 1000  # Items per chunk for large backups
        }
        
        logger.info(f"Backup manager initialized for {self.table_name}")
    
    def create_full_backup(self, backup_bucket: str, backup_name: Optional[str] = None,
                          include_migrations: bool = True) -> Dict[str, Any]:
        """Create a complete backup of the database"""
        
        try:
            if backup_name is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_name = f"echoes_backup_{self.environment}_{timestamp}"
            
            backup_prefix = f"backups/{backup_name}"
            backup_manifest = {
                'backup_name': backup_name,
                'environment': self.environment,
                'region': self.region,
                'timestamp': datetime.now().isoformat(),
                'tables': {},
                'metadata': {}
            }
            
            logger.info(f"Starting full backup: {backup_name}")
            
            # Backup main table
            logger.info("Backing up main table...")
            main_backup = self._backup_table(
                self.table_name, 
                backup_bucket, 
                f"{backup_prefix}/main_table"
            )
            backup_manifest['tables']['main'] = main_backup
            
            # Backup migrations table if requested and exists
            if include_migrations:
                try:
                    self.dynamodb.describe_table(TableName=self.migration_table)
                    logger.info("Backing up migrations table...")
                    migration_backup = self._backup_table(
                        self.migration_table,
                        backup_bucket,
                        f"{backup_prefix}/migrations"
                    )
                    backup_manifest['tables']['migrations'] = migration_backup
                except self.dynamodb.exceptions.ResourceNotFoundException:
                    logger.info("Migrations table not found, skipping")
            
            # Add table metadata
            backup_manifest['metadata'] = self._get_table_metadata()
            
            # Calculate backup statistics
            backup_manifest['statistics'] = self._calculate_backup_stats(backup_manifest)
            
            # Save manifest
            manifest_key = f"{backup_prefix}/manifest.json"
            manifest_content = json.dumps(backup_manifest, indent=2, default=str)
            
            if self.backup_config['compression']:
                manifest_content = gzip.compress(manifest_content.encode('utf-8'))
                manifest_key += '.gz'
            
            self.s3.put_object(
                Bucket=backup_bucket,
                Key=manifest_key,
                Body=manifest_content,
                ContentType='application/json',
                Metadata={
                    'backup-name': backup_name,
                    'environment': self.environment,
                    'backup-type': 'full'
                }
            )
            
            logger.info(f"Full backup completed: s3://{backup_bucket}/{backup_prefix}")
            
            backup_manifest['s3_location'] = {
                'bucket': backup_bucket,
                'prefix': backup_prefix,
                'manifest_key': manifest_key
            }
            
            return backup_manifest
            
        except Exception as e:
            logger.error(f"Error creating full backup: {e}")
            raise
    
    def create_incremental_backup(self, backup_bucket: str, last_backup_time: str,
                                 backup_name: Optional[str] = None) -> Dict[str, Any]:
        """Create an incremental backup since the last backup time"""
        
        try:
            if backup_name is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_name = f"echoes_incremental_{self.environment}_{timestamp}"
            
            backup_prefix = f"backups/incremental/{backup_name}"
            
            logger.info(f"Starting incremental backup since {last_backup_time}")
            
            # Parse last backup time
            last_backup_dt = datetime.fromisoformat(last_backup_time.replace('Z', '+00:00'))
            
            # Query for items modified since last backup
            table = self.dynamodb_resource.Table(self.table_name)
            
            # Use updatedAt field to filter (assuming it exists)
            # This is a simplified approach - in production, you might use DynamoDB Streams
            filter_expression = 'updatedAt > :last_backup'
            expression_values = {':last_backup': last_backup_dt.isoformat()}
            
            items = []
            scan_kwargs = {
                'FilterExpression': filter_expression,
                'ExpressionAttributeValues': expression_values
            }
            
            while True:
                response = table.scan(**scan_kwargs)
                items.extend(response['Items'])
                
                if 'LastEvaluatedKey' not in response:
                    break
                scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
                
                logger.info(f"Found {len(items)} items modified since last backup...")
            
            if not items:
                logger.info("No items modified since last backup")
                return {
                    'backup_name': backup_name,
                    'item_count': 0,
                    'message': 'No changes since last backup'
                }
            
            # Convert and compress data
            serializable_items = [self._convert_decimal_to_float(item) for item in items]
            data_content = json.dumps(serializable_items, indent=2)
            
            if self.backup_config['compression']:
                data_content = gzip.compress(data_content.encode('utf-8'))
            
            # Upload incremental data
            data_key = f"{backup_prefix}/data.json"
            if self.backup_config['compression']:
                data_key += '.gz'
            
            self.s3.put_object(
                Bucket=backup_bucket,
                Key=data_key,
                Body=data_content,
                ContentType='application/json',
                Metadata={
                    'backup-name': backup_name,
                    'environment': self.environment,
                    'backup-type': 'incremental',
                    'since': last_backup_time
                }
            )
            
            # Create manifest
            manifest = {
                'backup_name': backup_name,
                'backup_type': 'incremental',
                'environment': self.environment,
                'timestamp': datetime.now().isoformat(),
                'since': last_backup_time,
                'item_count': len(items),
                's3_location': {
                    'bucket': backup_bucket,
                    'key': data_key
                }
            }
            
            logger.info(f"Incremental backup completed: {len(items)} items")
            return manifest
            
        except Exception as e:
            logger.error(f"Error creating incremental backup: {e}")
            raise
    
    def restore_from_backup(self, backup_bucket: str, backup_path: str,
                           restore_options: Optional[Dict] = None) -> bool:
        """Restore database from backup"""
        
        try:
            if restore_options is None:
                restore_options = {
                    'overwrite_existing': False,
                    'restore_migrations': True,
                    'batch_size': 25,
                    'dry_run': False
                }
            
            logger.info(f"Starting restore from s3://{backup_bucket}/{backup_path}")
            
            # Check if this is a manifest-based backup or single file backup
            manifest_key = f"{backup_path}/manifest.json"
            try:
                # Try to get manifest (for full backups)
                manifest_response = self.s3.get_object(Bucket=backup_bucket, Key=manifest_key)
                manifest_data = json.loads(manifest_response['Body'].read())
                return self._restore_from_manifest(backup_bucket, manifest_data, restore_options)
                
            except self.s3.exceptions.NoSuchKey:
                # Try compressed manifest
                try:
                    manifest_response = self.s3.get_object(Bucket=backup_bucket, Key=f"{manifest_key}.gz")
                    manifest_data = json.loads(gzip.decompress(manifest_response['Body'].read()))
                    return self._restore_from_manifest(backup_bucket, manifest_data, restore_options)
                except self.s3.exceptions.NoSuchKey:
                    pass
            
            # Fall back to single file restore (legacy format)
            return self._restore_from_single_file(backup_bucket, backup_path, restore_options)
            
        except Exception as e:
            logger.error(f"Error during restore: {e}")
            return False
    
    def list_backups(self, backup_bucket: str, prefix: str = "backups/") -> List[Dict[str, Any]]:
        """List available backups in S3"""
        
        try:
            backups = []
            
            # List objects in backup prefix
            paginator = self.s3.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=backup_bucket, Prefix=prefix)
            
            manifest_keys = []
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        if obj['Key'].endswith('manifest.json') or obj['Key'].endswith('manifest.json.gz'):
                            manifest_keys.append(obj['Key'])
            
            # Get manifest details for each backup
            for manifest_key in manifest_keys:
                try:
                    response = self.s3.get_object(Bucket=backup_bucket, Key=manifest_key)
                    
                    if manifest_key.endswith('.gz'):
                        manifest_data = json.loads(gzip.decompress(response['Body'].read()))
                    else:
                        manifest_data = json.loads(response['Body'].read())
                    
                    backup_info = {
                        'backup_name': manifest_data.get('backup_name'),
                        'timestamp': manifest_data.get('timestamp'),
                        'environment': manifest_data.get('environment'),
                        'manifest_key': manifest_key,
                        'size_estimate': self._estimate_backup_size(manifest_data),
                        'item_count': self._get_backup_item_count(manifest_data)
                    }
                    
                    backups.append(backup_info)
                    
                except Exception as e:
                    logger.warning(f"Could not read manifest {manifest_key}: {e}")
                    continue
            
            # Sort by timestamp (newest first)
            backups.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return backups
            
        except Exception as e:
            logger.error(f"Error listing backups: {e}")
            return []
    
    def verify_backup(self, backup_bucket: str, backup_path: str) -> Dict[str, Any]:
        """Verify backup integrity and completeness"""
        
        try:
            logger.info(f"Verifying backup: s3://{backup_bucket}/{backup_path}")
            
            verification_result = {
                'backup_path': backup_path,
                'timestamp': datetime.now().isoformat(),
                'checks': {},
                'overall_status': 'unknown'
            }
            
            # Check 1: Manifest exists and is readable
            manifest_data = None
            manifest_key = f"{backup_path}/manifest.json"
            
            try:
                response = self.s3.get_object(Bucket=backup_bucket, Key=manifest_key)
                manifest_data = json.loads(response['Body'].read())
                verification_result['checks']['manifest'] = {'passed': True, 'message': 'Manifest readable'}
            except self.s3.exceptions.NoSuchKey:
                try:
                    response = self.s3.get_object(Bucket=backup_bucket, Key=f"{manifest_key}.gz")
                    manifest_data = json.loads(gzip.decompress(response['Body'].read()))
                    verification_result['checks']['manifest'] = {'passed': True, 'message': 'Compressed manifest readable'}
                except:
                    verification_result['checks']['manifest'] = {'passed': False, 'message': 'Manifest not found'}
            
            if not manifest_data:
                verification_result['overall_status'] = 'failed'
                return verification_result
            
            # Check 2: Verify referenced files exist
            file_checks = []
            
            if 'tables' in manifest_data:
                for table_name, table_info in manifest_data['tables'].items():
                    if 'files' in table_info:
                        for file_info in table_info['files']:
                            s3_key = file_info['s3_key']
                            try:
                                self.s3.head_object(Bucket=backup_bucket, Key=s3_key)
                                file_checks.append({'file': s3_key, 'exists': True})
                            except self.s3.exceptions.NoSuchKey:
                                file_checks.append({'file': s3_key, 'exists': False})
            
            files_exist = all(check['exists'] for check in file_checks)
            verification_result['checks']['files'] = {
                'passed': files_exist,
                'message': f"{len([c for c in file_checks if c['exists']])}/{len(file_checks)} files exist"
            }
            
            # Check 3: Sample data validation (read a small sample)
            if files_exist and manifest_data.get('tables', {}).get('main'):
                try:
                    main_table_files = manifest_data['tables']['main']['files']
                    if main_table_files:
                        # Read first file to validate format
                        first_file = main_table_files[0]['s3_key']
                        response = self.s3.get_object(Bucket=backup_bucket, Key=first_file)
                        
                        content = response['Body'].read()
                        if first_file.endswith('.gz'):
                            content = gzip.decompress(content)
                        
                        sample_data = json.loads(content)
                        
                        # Basic validation
                        if isinstance(sample_data, list) and len(sample_data) > 0:
                            sample_item = sample_data[0]
                            has_required_fields = all(field in sample_item for field in ['userId', 'timestamp', 'echoId'])
                            
                            verification_result['checks']['data_format'] = {
                                'passed': has_required_fields,
                                'message': f"Sample validation: {len(sample_data)} items, required fields: {has_required_fields}"
                            }
                        else:
                            verification_result['checks']['data_format'] = {
                                'passed': False,
                                'message': "Invalid data format in backup file"
                            }
                            
                except Exception as e:
                    verification_result['checks']['data_format'] = {
                        'passed': False,
                        'message': f"Could not validate data format: {str(e)}"
                    }
            
            # Overall status
            all_checks_passed = all(check['passed'] for check in verification_result['checks'].values())
            verification_result['overall_status'] = 'passed' if all_checks_passed else 'failed'
            
            return verification_result
            
        except Exception as e:
            logger.error(f"Error verifying backup: {e}")
            return {
                'backup_path': backup_path,
                'overall_status': 'error',
                'error': str(e)
            }
    
    def cleanup_old_backups(self, backup_bucket: str, retention_days: int = 30,
                           keep_weekly: int = 4, keep_monthly: int = 12) -> Dict[str, Any]:
        """Clean up old backups based on retention policy"""
        
        try:
            logger.info(f"Cleaning up backups older than {retention_days} days")
            
            # Get all backups
            backups = self.list_backups(backup_bucket)
            
            if not backups:
                return {'deleted_count': 0, 'message': 'No backups found'}
            
            now = datetime.now()
            cutoff_date = now - timedelta(days=retention_days)
            
            # Categorize backups
            to_delete = []
            to_keep = []
            weekly_keepers = []
            monthly_keepers = []
            
            for backup in backups:
                backup_time = datetime.fromisoformat(backup['timestamp'].replace('Z', '+00:00'))
                
                if backup_time > cutoff_date:
                    # Keep recent backups
                    to_keep.append(backup)
                else:
                    # Apply retention policy for older backups
                    week_number = backup_time.isocalendar()[1]
                    month = backup_time.month
                    
                    # Keep one backup per week for the specified number of weeks
                    week_key = f"{backup_time.year}-W{week_number}"
                    if week_key not in [w['key'] for w in weekly_keepers] and len(weekly_keepers) < keep_weekly:
                        weekly_keepers.append({'key': week_key, 'backup': backup})
                        to_keep.append(backup)
                        continue
                    
                    # Keep one backup per month for the specified number of months
                    month_key = f"{backup_time.year}-{month:02d}"
                    if month_key not in [m['key'] for m in monthly_keepers] and len(monthly_keepers) < keep_monthly:
                        monthly_keepers.append({'key': month_key, 'backup': backup})
                        to_keep.append(backup)
                        continue
                    
                    # Mark for deletion
                    to_delete.append(backup)
            
            # Delete old backups
            deleted_count = 0
            for backup in to_delete:
                try:
                    # Get backup prefix from manifest key
                    manifest_key = backup['manifest_key']
                    backup_prefix = '/'.join(manifest_key.split('/')[:-1])  # Remove manifest.json part
                    
                    # List and delete all objects in backup prefix
                    paginator = self.s3.get_paginator('list_objects_v2')
                    pages = paginator.paginate(Bucket=backup_bucket, Prefix=backup_prefix)
                    
                    objects_to_delete = []
                    for page in pages:
                        if 'Contents' in page:
                            for obj in page['Contents']:
                                objects_to_delete.append({'Key': obj['Key']})
                    
                    if objects_to_delete:
                        # Delete in batches
                        for i in range(0, len(objects_to_delete), 1000):
                            batch = objects_to_delete[i:i+1000]
                            self.s3.delete_objects(
                                Bucket=backup_bucket,
                                Delete={'Objects': batch}
                            )
                    
                    deleted_count += 1
                    logger.info(f"Deleted backup: {backup['backup_name']}")
                    
                except Exception as e:
                    logger.error(f"Error deleting backup {backup['backup_name']}: {e}")
            
            cleanup_result = {
                'deleted_count': deleted_count,
                'kept_count': len(to_keep),
                'retention_policy': {
                    'retention_days': retention_days,
                    'keep_weekly': keep_weekly,
                    'keep_monthly': keep_monthly
                },
                'summary': f"Deleted {deleted_count} old backups, kept {len(to_keep)} backups"
            }
            
            logger.info(cleanup_result['summary'])
            return cleanup_result
            
        except Exception as e:
            logger.error(f"Error cleaning up backups: {e}")
            return {'error': str(e)}
    
    def _backup_table(self, table_name: str, backup_bucket: str, s3_prefix: str) -> Dict[str, Any]:
        """Backup a single table to S3"""
        
        try:
            table = self.dynamodb_resource.Table(table_name)
            
            # Get table info
            table_info = self.dynamodb.describe_table(TableName=table_name)['Table']
            
            # Scan all items with parallel workers
            items = []
            scan_kwargs = {}
            
            logger.info(f"Scanning table {table_name}...")
            
            # Use parallel scanning for better performance
            if self.backup_config['max_workers'] > 1:
                items = self._parallel_scan(table, scan_kwargs)
            else:
                while True:
                    response = table.scan(**scan_kwargs)
                    items.extend(response['Items'])
                    
                    if 'LastEvaluatedKey' not in response:
                        break
                    scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
                    
                    if len(items) % 1000 == 0:
                        logger.info(f"Scanned {len(items)} items...")
            
            logger.info(f"Scanned {len(items)} total items from {table_name}")
            
            # Convert Decimal to float for JSON serialization
            serializable_items = [self._convert_decimal_to_float(item) for item in items]
            
            # Split into chunks if too large
            files = []
            chunk_size = self.backup_config['chunk_size']
            
            for i in range(0, len(serializable_items), chunk_size):
                chunk = serializable_items[i:i + chunk_size]
                chunk_index = i // chunk_size
                
                # Prepare data
                data_content = json.dumps(chunk, indent=2)
                
                # Compress if enabled
                if self.backup_config['compression']:
                    data_content = gzip.compress(data_content.encode('utf-8'))
                
                # Generate S3 key
                s3_key = f"{s3_prefix}/data_{chunk_index:04d}.json"
                if self.backup_config['compression']:
                    s3_key += '.gz'
                
                # Upload chunk
                self.s3.put_object(
                    Bucket=backup_bucket,
                    Key=s3_key,
                    Body=data_content,
                    ContentType='application/json',
                    Metadata={
                        'table-name': table_name,
                        'chunk-index': str(chunk_index),
                        'item-count': str(len(chunk))
                    }
                )
                
                files.append({
                    's3_key': s3_key,
                    'chunk_index': chunk_index,
                    'item_count': len(chunk),
                    'compressed': self.backup_config['compression']
                })
                
                logger.info(f"Uploaded chunk {chunk_index + 1} ({len(chunk)} items)")
            
            backup_info = {
                'table_name': table_name,
                'item_count': len(items),
                'files': files,
                'table_info': {
                    'status': table_info['TableStatus'],
                    'creation_date': table_info['CreationDateTime'].isoformat(),
                    'item_count': table_info.get('ItemCount', len(items)),
                    'table_size_bytes': table_info.get('TableSizeBytes', 0)
                }
            }
            
            return backup_info
            
        except Exception as e:
            logger.error(f"Error backing up table {table_name}: {e}")
            raise
    
    def _parallel_scan(self, table, base_scan_kwargs: Dict) -> List[Dict]:
        """Perform parallel scan of DynamoDB table"""
        
        max_workers = self.backup_config['max_workers']
        items = []
        items_lock = threading.Lock()
        
        def scan_segment(segment: int, total_segments: int):
            segment_items = []
            scan_kwargs = base_scan_kwargs.copy()
            scan_kwargs['Segment'] = segment
            scan_kwargs['TotalSegments'] = total_segments
            
            while True:
                response = table.scan(**scan_kwargs)
                segment_items.extend(response['Items'])
                
                if 'LastEvaluatedKey' not in response:
                    break
                scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
            
            with items_lock:
                items.extend(segment_items)
                logger.info(f"Segment {segment} completed: {len(segment_items)} items")
        
        # Run parallel scans
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for segment in range(max_workers):
                future = executor.submit(scan_segment, segment, max_workers)
                futures.append(future)
            
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error in parallel scan segment: {e}")
                    raise
        
        return items
    
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
    
    def _get_table_metadata(self) -> Dict[str, Any]:
        """Get metadata about tables for backup manifest"""
        
        metadata = {}
        
        try:
            # Main table metadata
            main_table_info = self.dynamodb.describe_table(TableName=self.table_name)['Table']
            metadata['main_table'] = {
                'table_name': self.table_name,
                'status': main_table_info['TableStatus'],
                'item_count': main_table_info.get('ItemCount', 0),
                'table_size_bytes': main_table_info.get('TableSizeBytes', 0),
                'gsi_count': len(main_table_info.get('GlobalSecondaryIndexes', [])),
                'billing_mode': main_table_info.get('BillingModeSummary', {}).get('BillingMode')
            }
            
            # Migration table metadata (if exists)
            try:
                migration_table_info = self.dynamodb.describe_table(TableName=self.migration_table)['Table']
                metadata['migration_table'] = {
                    'table_name': self.migration_table,
                    'status': migration_table_info['TableStatus'],
                    'item_count': migration_table_info.get('ItemCount', 0)
                }
            except self.dynamodb.exceptions.ResourceNotFoundException:
                pass
                
        except Exception as e:
            logger.warning(f"Could not get table metadata: {e}")
        
        return metadata
    
    def _calculate_backup_stats(self, manifest: Dict) -> Dict[str, Any]:
        """Calculate backup statistics"""
        
        stats = {
            'total_items': 0,
            'total_files': 0,
            'estimated_size_bytes': 0
        }
        
        for table_name, table_info in manifest.get('tables', {}).items():
            stats['total_items'] += table_info.get('item_count', 0)
            stats['total_files'] += len(table_info.get('files', []))
        
        return stats
    
    def _estimate_backup_size(self, manifest_data: Dict) -> str:
        """Estimate backup size from manifest"""
        
        total_items = 0
        for table_info in manifest_data.get('tables', {}).values():
            total_items += table_info.get('item_count', 0)
        
        # Rough estimate: ~1KB per item (very approximate)
        estimated_bytes = total_items * 1024
        
        if estimated_bytes < 1024 * 1024:
            return f"{estimated_bytes / 1024:.1f} KB"
        elif estimated_bytes < 1024 * 1024 * 1024:
            return f"{estimated_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{estimated_bytes / (1024 * 1024 * 1024):.1f} GB"
    
    def _get_backup_item_count(self, manifest_data: Dict) -> int:
        """Get total item count from manifest"""
        
        total_items = 0
        for table_info in manifest_data.get('tables', {}).values():
            total_items += table_info.get('item_count', 0)
        return total_items
    
    def _restore_from_manifest(self, backup_bucket: str, manifest_data: Dict,
                              restore_options: Dict) -> bool:
        """Restore from a manifest-based backup"""
        
        try:
            logger.info("Restoring from manifest-based backup")
            
            if restore_options.get('dry_run', False):
                logger.info("DRY RUN: Would restore the following:")
                for table_name, table_info in manifest_data.get('tables', {}).items():
                    logger.info(f"  {table_name}: {table_info.get('item_count', 0)} items")
                return True
            
            # Restore main table
            if 'main' in manifest_data.get('tables', {}):
                main_table_info = manifest_data['tables']['main']
                success = self._restore_table_data(
                    backup_bucket,
                    main_table_info,
                    self.table_name,
                    restore_options
                )
                if not success:
                    return False
            
            # Restore migrations table if requested
            if (restore_options.get('restore_migrations', True) and 
                'migrations' in manifest_data.get('tables', {})):
                migration_table_info = manifest_data['tables']['migrations']
                success = self._restore_table_data(
                    backup_bucket,
                    migration_table_info,
                    self.migration_table,
                    restore_options
                )
                if not success:
                    logger.warning("Failed to restore migrations table, continuing...")
            
            logger.info("Restore completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error restoring from manifest: {e}")
            return False
    
    def _restore_from_single_file(self, backup_bucket: str, backup_path: str,
                                 restore_options: Dict) -> bool:
        """Restore from a single backup file (legacy format)"""
        
        try:
            logger.info("Restoring from single file backup")
            
            # Try different file extensions
            possible_keys = [
                f"{backup_path}/data.json",
                f"{backup_path}/data.json.gz",
                backup_path  # In case backup_path is the full key
            ]
            
            data = None
            for key in possible_keys:
                try:
                    response = self.s3.get_object(Bucket=backup_bucket, Key=key)
                    content = response['Body'].read()
                    
                    if key.endswith('.gz'):
                        content = gzip.decompress(content)
                    
                    data = json.loads(content)
                    break
                    
                except self.s3.exceptions.NoSuchKey:
                    continue
            
            if data is None:
                logger.error(f"Could not find backup data at {backup_path}")
                return False
            
            if restore_options.get('dry_run', False):
                logger.info(f"DRY RUN: Would restore {len(data)} items")
                return True
            
            # Restore data to main table
            table = self.dynamodb_resource.Table(self.table_name)
            batch_size = restore_options.get('batch_size', 25)
            
            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                
                with table.batch_writer() as writer:
                    for item in batch:
                        # Convert floats back to Decimal
                        item = self._convert_floats_to_decimal(item)
                        
                        if restore_options.get('overwrite_existing', False):
                            writer.put_item(Item=item)
                        else:
                            # Try to avoid overwriting existing items
                            try:
                                table.put_item(
                                    Item=item,
                                    ConditionExpression='attribute_not_exists(userId) AND attribute_not_exists(#ts)',
                                    ExpressionAttributeNames={'#ts': 'timestamp'}
                                )
                            except self.dynamodb.exceptions.ConditionalCheckFailedException:
                                # Item already exists, skip if not overwriting
                                continue
                
                logger.info(f"Restored {min(i + batch_size, len(data))} / {len(data)} items")
            
            logger.info(f"Single file restore completed: {len(data)} items")
            return True
            
        except Exception as e:
            logger.error(f"Error restoring from single file: {e}")
            return False
    
    def _restore_table_data(self, backup_bucket: str, table_info: Dict, 
                           target_table: str, restore_options: Dict) -> bool:
        """Restore data for a specific table from backup files"""
        
        try:
            table = self.dynamodb_resource.Table(target_table)
            batch_size = restore_options.get('batch_size', 25)
            
            # Process each backup file
            for file_info in table_info.get('files', []):
                s3_key = file_info['s3_key']
                
                # Download and decompress file
                response = self.s3.get_object(Bucket=backup_bucket, Key=s3_key)
                content = response['Body'].read()
                
                if file_info.get('compressed', False):
                    content = gzip.decompress(content)
                
                items = json.loads(content)
                
                # Restore items in batches
                for i in range(0, len(items), batch_size):
                    batch = items[i:i + batch_size]
                    
                    with table.batch_writer() as writer:
                        for item in batch:
                            # Convert floats back to Decimal
                            item = self._convert_floats_to_decimal(item)
                            
                            if restore_options.get('overwrite_existing', False):
                                writer.put_item(Item=item)
                            else:
                                # Try to avoid overwriting existing items
                                try:
                                    table.put_item(
                                        Item=item,
                                        ConditionExpression='attribute_not_exists(userId) AND attribute_not_exists(#ts)',
                                        ExpressionAttributeNames={'#ts': 'timestamp'}
                                    )
                                except self.dynamodb.exceptions.ConditionalCheckFailedException:
                                    continue
                
                logger.info(f"Restored file {s3_key}: {len(items)} items")
            
            return True
            
        except Exception as e:
            logger.error(f"Error restoring table data: {e}")
            return False


def main():
    """Main CLI interface for backup operations"""
    
    parser = argparse.ArgumentParser(
        description='Echoes Database Backup Utilities',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create full backup
  python backup_utils.py backup --bucket my-backups --name daily_backup_20250628

  # Create incremental backup
  python backup_utils.py incremental --bucket my-backups --since 2025-06-27T00:00:00

  # List backups
  python backup_utils.py list --bucket my-backups

  # Restore from backup
  python backup_utils.py restore --bucket my-backups --path backups/daily_backup_20250628

  # Verify backup
  python backup_utils.py verify --bucket my-backups --path backups/daily_backup_20250628

  # Cleanup old backups
  python backup_utils.py cleanup --bucket my-backups --retention-days 30
        """
    )
    
    parser.add_argument('command', choices=[
        'backup', 'incremental', 'restore', 'list', 'verify', 'cleanup'
    ], help='Command to execute')
    
    parser.add_argument('--environment', default='dev', choices=['dev', 'staging', 'prod'])
    parser.add_argument('--region', default='us-east-1')
    parser.add_argument('--bucket', required=True, help='S3 bucket for backup operations')
    parser.add_argument('--name', help='Backup name')
    parser.add_argument('--path', help='Backup path for restore/verify operations')
    parser.add_argument('--since', help='Since timestamp for incremental backup (ISO format)')
    parser.add_argument('--retention-days', type=int, default=30, help='Retention period in days')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing data during restore')
    parser.add_argument('--dry-run', action='store_true', help='Dry run for restore operations')
    parser.add_argument('--output', choices=['text', 'json'], default='text', help='Output format')
    
    args = parser.parse_args()
    
    # Initialize backup manager
    try:
        manager = BackupManager(region=args.region, environment=args.environment)
    except Exception as e:
        logger.error(f"Failed to initialize backup manager: {e}")
        return False
    
    # Execute command
    try:
        if args.command == 'backup':
            result = manager.create_full_backup(args.bucket, args.name)
            if args.output == 'json':
                print(json.dumps(result, indent=2, default=str))
            else:
                print(f"Backup completed: {result['backup_name']}")
                print(f"Items backed up: {result['statistics']['total_items']}")
                print(f"Files created: {result['statistics']['total_files']}")
        
        elif args.command == 'incremental':
            if not args.since:
                logger.error("--since required for incremental backup")
                return False
            result = manager.create_incremental_backup(args.bucket, args.since, args.name)
            if args.output == 'json':
                print(json.dumps(result, indent=2, default=str))
            else:
                print(f"Incremental backup completed: {result.get('item_count', 0)} items")
        
        elif args.command == 'restore':
            if not args.path:
                logger.error("--path required for restore")
                return False
            restore_options = {
                'overwrite_existing': args.overwrite,
                'dry_run': args.dry_run
            }
            success = manager.restore_from_backup(args.bucket, args.path, restore_options)
            if not success:
                return False
        
        elif args.command == 'list':
            backups = manager.list_backups(args.bucket)
            if args.output == 'json':
                print(json.dumps(backups, indent=2, default=str))
            else:
                print(f"Found {len(backups)} backups:")
                for backup in backups:
                    print(f"  {backup['backup_name']} ({backup['timestamp']}) - {backup['item_count']} items")
        
        elif args.command == 'verify':
            if not args.path:
                logger.error("--path required for verify")
                return False
            result = manager.verify_backup(args.bucket, args.path)
            if args.output == 'json':
                print(json.dumps(result, indent=2, default=str))
            else:
                print(f"Verification result: {result['overall_status']}")
                for check_name, check_result in result['checks'].items():
                    status = "✓" if check_result['passed'] else "✗"
                    print(f"  {status} {check_name}: {check_result['message']}")
        
        elif args.command == 'cleanup':
            result = manager.cleanup_old_backups(args.bucket, args.retention_days)
            if args.output == 'json':
                print(json.dumps(result, indent=2, default=str))
            else:
                print(result.get('summary', 'Cleanup completed'))
        
        return True
        
    except Exception as e:
        logger.error(f"Command failed: {e}")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)