#!/usr/bin/env python3
"""
Echoes Database Health Check - Comprehensive database connectivity and performance monitoring
"""

import boto3
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import argparse
import sys
from decimal import Decimal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseHealthChecker:
    """Comprehensive health checking for Echoes DynamoDB setup"""
    
    def __init__(self, region: str = 'us-east-1', environment: str = 'dev'):
        self.region = region
        self.environment = environment
        self.table_name = f'EchoesTable-{environment}'
        self.migration_table = f'EchoesMigrations-{environment}'
        
        # Initialize AWS clients
        try:
            self.dynamodb = boto3.client('dynamodb', region_name=region)
            self.dynamodb_resource = boto3.resource('dynamodb', region_name=region)
            self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {e}")
            raise
        
        # Health check results
        self.health_results = {
            'timestamp': datetime.now().isoformat(),
            'environment': environment,
            'region': region,
            'overall_status': 'unknown',
            'checks': {}
        }
        
        logger.info(f"Health checker initialized for {self.table_name}")
    
    def run_all_checks(self, quick: bool = False) -> Dict[str, Any]:
        """Run all health checks and return comprehensive results"""
        
        logger.info("Starting comprehensive database health check...")
        
        checks = [
            ('connectivity', self.check_connectivity),
            ('table_status', self.check_table_status),
            ('gsi_status', self.check_gsi_status),
            ('basic_operations', self.check_basic_operations),
            ('migration_status', self.check_migration_status),
        ]
        
        if not quick:
            checks.extend([
                ('performance', self.check_performance),
                ('data_integrity', self.check_data_integrity),
                ('capacity_metrics', self.check_capacity_metrics),
                ('error_rates', self.check_error_rates)
            ])
        
        # Run each check
        all_passed = True
        for check_name, check_function in checks:
            logger.info(f"Running {check_name} check...")
            try:
                result = check_function()
                self.health_results['checks'][check_name] = result
                
                if not result['passed']:
                    all_passed = False
                    logger.warning(f"{check_name} check failed: {result['message']}")
                else:
                    logger.info(f"{check_name} check passed")
                    
            except Exception as e:
                logger.error(f"Error running {check_name} check: {e}")
                self.health_results['checks'][check_name] = {
                    'passed': False,
                    'message': f"Check failed with error: {str(e)}",
                    'error': str(e)
                }
                all_passed = False
        
        # Set overall status
        self.health_results['overall_status'] = 'healthy' if all_passed else 'unhealthy'
        self.health_results['summary'] = self._generate_summary()
        
        logger.info(f"Health check completed. Overall status: {self.health_results['overall_status']}")
        
        return self.health_results
    
    def check_connectivity(self) -> Dict[str, Any]:
        """Test basic AWS DynamoDB connectivity"""
        
        try:
            # Test basic AWS credentials and connectivity
            response = self.dynamodb.list_tables()
            
            # Check if our tables are in the list
            tables = response.get('TableNames', [])
            main_table_exists = self.table_name in tables
            migration_table_exists = self.migration_table in tables
            
            if main_table_exists:
                message = "Successfully connected to DynamoDB and found main table"
                passed = True
            else:
                message = f"Connected to DynamoDB but table {self.table_name} not found"
                passed = False
            
            return {
                'passed': passed,
                'message': message,
                'details': {
                    'region': self.region,
                    'main_table_exists': main_table_exists,
                    'migration_table_exists': migration_table_exists,
                    'total_tables': len(tables)
                }
            }
            
        except Exception as e:
            return {
                'passed': False,
                'message': f"Failed to connect to DynamoDB: {str(e)}",
                'error': str(e)
            }
    
    def check_table_status(self) -> Dict[str, Any]:
        """Check main table status and configuration"""
        
        try:
            response = self.dynamodb.describe_table(TableName=self.table_name)
            table_info = response['Table']
            
            status = table_info['TableStatus']
            item_count = table_info.get('ItemCount', 0)
            table_size = table_info.get('TableSizeBytes', 0)
            
            # Check if table is active
            passed = status == 'ACTIVE'
            
            # Additional checks
            has_stream = 'StreamSpecification' in table_info and table_info['StreamSpecification']['StreamEnabled']
            has_encryption = table_info.get('SSEDescription', {}).get('Status') == 'ENABLED'
            has_ttl = self._check_ttl_status()
            
            message = f"Table status: {status}"
            if not passed:
                message += f" (Expected: ACTIVE)"
            
            return {
                'passed': passed,
                'message': message,
                'details': {
                    'status': status,
                    'item_count': item_count,
                    'table_size_bytes': table_size,
                    'creation_date': table_info['CreationDateTime'].isoformat(),
                    'billing_mode': table_info.get('BillingModeSummary', {}).get('BillingMode'),
                    'has_stream': has_stream,
                    'has_encryption': has_encryption,
                    'has_ttl': has_ttl
                }
            }
            
        except self.dynamodb.exceptions.ResourceNotFoundException:
            return {
                'passed': False,
                'message': f"Table {self.table_name} does not exist",
                'error': 'ResourceNotFoundException'
            }
        except Exception as e:
            return {
                'passed': False,
                'message': f"Error checking table status: {str(e)}",
                'error': str(e)
            }
    
    def check_gsi_status(self) -> Dict[str, Any]:
        """Check Global Secondary Index status"""
        
        try:
            response = self.dynamodb.describe_table(TableName=self.table_name)
            table_info = response['Table']
            
            if 'GlobalSecondaryIndexes' not in table_info:
                return {
                    'passed': False,
                    'message': "No Global Secondary Indexes found",
                    'details': {'gsi_count': 0}
                }
            
            gsis = table_info['GlobalSecondaryIndexes']
            gsi_statuses = []
            all_active = True
            
            expected_gsis = [
                'emotion-timestamp-index',
                'echoId-index',
                'userId-emotion-index'
            ]
            
            for gsi in gsis:
                gsi_name = gsi['IndexName']
                gsi_status = gsi['IndexStatus']
                gsi_statuses.append({
                    'name': gsi_name,
                    'status': gsi_status,
                    'item_count': gsi.get('ItemCount', 0)
                })
                
                if gsi_status != 'ACTIVE':
                    all_active = False
            
            # Check if all expected GSIs are present
            found_gsi_names = [gsi['IndexName'] for gsi in gsis]
            missing_gsis = [name for name in expected_gsis if name not in found_gsi_names]
            
            passed = all_active and len(missing_gsis) == 0
            
            message = f"Found {len(gsis)} GSIs"
            if not all_active:
                message += " (some not active)"
            if missing_gsis:
                message += f" (missing: {', '.join(missing_gsis)})"
            
            return {
                'passed': passed,
                'message': message,
                'details': {
                    'gsi_count': len(gsis),
                    'gsi_statuses': gsi_statuses,
                    'all_active': all_active,
                    'missing_gsis': missing_gsis
                }
            }
            
        except Exception as e:
            return {
                'passed': False,
                'message': f"Error checking GSI status: {str(e)}",
                'error': str(e)
            }
    
    def check_basic_operations(self) -> Dict[str, Any]:
        """Test basic CRUD operations"""
        
        try:
            table = self.dynamodb_resource.Table(self.table_name)
            
            # Test 1: Read operation (scan with limit)
            scan_response = table.scan(Limit=1)
            can_read = 'Items' in scan_response
            
            # Test 2: Query operations on GSIs (if data exists)
            can_query_gsi = True
            gsi_tests = []
            
            if can_read and scan_response['Items']:
                sample_item = scan_response['Items'][0]
                
                # Test emotion-timestamp-index
                try:
                    emotion_response = table.query(
                        IndexName='emotion-timestamp-index',
                        KeyConditionExpression='emotion = :emotion',
                        ExpressionAttributeValues={':emotion': sample_item['emotion']},
                        Limit=1
                    )
                    gsi_tests.append({
                        'index': 'emotion-timestamp-index',
                        'passed': len(emotion_response['Items']) > 0
                    })
                except Exception as e:
                    gsi_tests.append({
                        'index': 'emotion-timestamp-index',
                        'passed': False,
                        'error': str(e)
                    })
                    can_query_gsi = False
                
                # Test echoId-index
                try:
                    echo_response = table.query(
                        IndexName='echoId-index',
                        KeyConditionExpression='echoId = :echoId',
                        ExpressionAttributeValues={':echoId': sample_item['echoId']},
                        Limit=1
                    )
                    gsi_tests.append({
                        'index': 'echoId-index',
                        'passed': len(echo_response['Items']) > 0
                    })
                except Exception as e:
                    gsi_tests.append({
                        'index': 'echoId-index',
                        'passed': False,
                        'error': str(e)
                    })
                    can_query_gsi = False
            
            # Test 3: Write operation (put a test item)
            test_item = {
                'userId': 'health_check_user',
                'timestamp': datetime.now().isoformat(),
                'echoId': 'health_check_echo',
                'emotion': 'testing',
                'tags': ['health_check'],
                'createdAt': datetime.now().isoformat(),
                'metadata': {'test': True}
            }
            
            can_write = True
            try:
                table.put_item(Item=test_item)
                
                # Verify the write by reading it back
                get_response = table.get_item(
                    Key={
                        'userId': test_item['userId'],
                        'timestamp': test_item['timestamp']
                    }
                )
                
                if 'Item' not in get_response:
                    can_write = False
                else:
                    # Clean up test item
                    table.delete_item(
                        Key={
                            'userId': test_item['userId'],
                            'timestamp': test_item['timestamp']
                        }
                    )
                    
            except Exception as e:
                logger.warning(f"Write test failed: {e}")
                can_write = False
            
            passed = can_read and can_query_gsi and can_write
            
            operations_status = []
            operations_status.append(f"Read: {'✓' if can_read else '✗'}")
            operations_status.append(f"Query GSI: {'✓' if can_query_gsi else '✗'}")
            operations_status.append(f"Write: {'✓' if can_write else '✗'}")
            
            message = f"Basic operations - {', '.join(operations_status)}"
            
            return {
                'passed': passed,
                'message': message,
                'details': {
                    'can_read': can_read,
                    'can_query_gsi': can_query_gsi,
                    'can_write': can_write,
                    'gsi_tests': gsi_tests,
                    'has_data': can_read and len(scan_response['Items']) > 0
                }
            }
            
        except Exception as e:
            return {
                'passed': False,
                'message': f"Error testing basic operations: {str(e)}",
                'error': str(e)
            }
    
    def check_migration_status(self) -> Dict[str, Any]:
        """Check migration table and applied migrations"""
        
        try:
            # Check if migration table exists
            try:
                migration_table = self.dynamodb_resource.Table(self.migration_table)
                migration_response = migration_table.scan()
                
                applied_migrations = migration_response['Items']
                migration_count = len(applied_migrations)
                
                # Get latest migration
                latest_migration = None
                if applied_migrations:
                    latest_migration = max(applied_migrations, key=lambda x: x['version'])
                
                passed = migration_count > 0
                message = f"Found {migration_count} applied migrations"
                
                return {
                    'passed': passed,
                    'message': message,
                    'details': {
                        'migration_table_exists': True,
                        'applied_count': migration_count,
                        'latest_migration': latest_migration['version'] if latest_migration else None,
                        'latest_applied_at': latest_migration['applied_at'] if latest_migration else None
                    }
                }
                
            except self.dynamodb.exceptions.ResourceNotFoundException:
                return {
                    'passed': False,
                    'message': "Migration table does not exist",
                    'details': {
                        'migration_table_exists': False,
                        'applied_count': 0
                    }
                }
                
        except Exception as e:
            return {
                'passed': False,
                'message': f"Error checking migration status: {str(e)}",
                'error': str(e)
            }
    
    def check_performance(self) -> Dict[str, Any]:
        """Test database performance with timing"""
        
        try:
            table = self.dynamodb_resource.Table(self.table_name)
            performance_metrics = {}
            
            # Test 1: Scan performance
            start_time = time.time()
            scan_response = table.scan(Limit=10)
            scan_time = time.time() - start_time
            performance_metrics['scan_time_ms'] = round(scan_time * 1000, 2)
            
            # Test 2: Query performance (if data exists)
            if scan_response['Items']:
                sample_item = scan_response['Items'][0]
                
                # Primary key query
                start_time = time.time()
                query_response = table.query(
                    KeyConditionExpression='userId = :userId',
                    ExpressionAttributeValues={':userId': sample_item['userId']},
                    Limit=5
                )
                query_time = time.time() - start_time
                performance_metrics['primary_query_time_ms'] = round(query_time * 1000, 2)
                
                # GSI query
                start_time = time.time()
                gsi_response = table.query(
                    IndexName='emotion-timestamp-index',
                    KeyConditionExpression='emotion = :emotion',
                    ExpressionAttributeValues={':emotion': sample_item['emotion']},
                    Limit=5
                )
                gsi_query_time = time.time() - start_time
                performance_metrics['gsi_query_time_ms'] = round(gsi_query_time * 1000, 2)
            
            # Performance thresholds (milliseconds)
            scan_threshold = 1000  # 1 second
            query_threshold = 500  # 500ms
            
            passed = True
            issues = []
            
            if performance_metrics.get('scan_time_ms', 0) > scan_threshold:
                passed = False
                issues.append(f"Scan time too high: {performance_metrics['scan_time_ms']}ms")
            
            if performance_metrics.get('primary_query_time_ms', 0) > query_threshold:
                passed = False
                issues.append(f"Primary query time too high: {performance_metrics['primary_query_time_ms']}ms")
            
            if performance_metrics.get('gsi_query_time_ms', 0) > query_threshold:
                passed = False
                issues.append(f"GSI query time too high: {performance_metrics['gsi_query_time_ms']}ms")
            
            message = "Performance within acceptable limits" if passed else f"Performance issues: {', '.join(issues)}"
            
            return {
                'passed': passed,
                'message': message,
                'details': performance_metrics
            }
            
        except Exception as e:
            return {
                'passed': False,
                'message': f"Error checking performance: {str(e)}",
                'error': str(e)
            }
    
    def check_data_integrity(self) -> Dict[str, Any]:
        """Check data integrity and consistency"""
        
        try:
            table = self.dynamodb_resource.Table(self.table_name)
            
            # Sample some data for integrity checks
            scan_response = table.scan(Limit=50)
            items = scan_response['Items']
            
            if not items:
                return {
                    'passed': True,
                    'message': "No data to check (empty table)",
                    'details': {'item_count': 0}
                }
            
            integrity_issues = []
            checked_fields = {
                'required_fields': 0,
                'valid_timestamps': 0,
                'valid_emotions': 0,
                'valid_echo_ids': 0
            }
            
            for item in items:
                # Check required fields
                required_fields = ['userId', 'timestamp', 'echoId', 'emotion']
                if all(field in item for field in required_fields):
                    checked_fields['required_fields'] += 1
                else:
                    integrity_issues.append(f"Missing required fields in item: {item.get('echoId', 'unknown')}")
                
                # Check timestamp format
                try:
                    datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00'))
                    checked_fields['valid_timestamps'] += 1
                except Exception:
                    integrity_issues.append(f"Invalid timestamp format: {item.get('timestamp')}")
                
                # Check emotion field
                if isinstance(item.get('emotion'), str) and len(item['emotion']) > 0:
                    checked_fields['valid_emotions'] += 1
                else:
                    integrity_issues.append(f"Invalid emotion field: {item.get('emotion')}")
                
                # Check echo ID format
                if isinstance(item.get('echoId'), str) and len(item['echoId']) > 0:
                    checked_fields['valid_echo_ids'] += 1
                else:
                    integrity_issues.append(f"Invalid echoId: {item.get('echoId')}")
            
            # Calculate integrity score
            total_items = len(items)
            integrity_score = min(checked_fields.values()) / total_items if total_items > 0 else 0
            
            passed = integrity_score >= 0.95 and len(integrity_issues) == 0
            
            message = f"Data integrity score: {integrity_score:.2%}"
            if integrity_issues:
                message += f" ({len(integrity_issues)} issues found)"
            
            return {
                'passed': passed,
                'message': message,
                'details': {
                    'items_checked': total_items,
                    'integrity_score': integrity_score,
                    'field_validation': checked_fields,
                    'issues': integrity_issues[:10]  # Limit to first 10 issues
                }
            }
            
        except Exception as e:
            return {
                'passed': False,
                'message': f"Error checking data integrity: {str(e)}",
                'error': str(e)
            }
    
    def check_capacity_metrics(self) -> Dict[str, Any]:
        """Check capacity and CloudWatch metrics"""
        
        try:
            # Get recent CloudWatch metrics
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=1)
            
            metrics = {}
            
            # Common metric names for DynamoDB
            metric_names = [
                'ConsumedReadCapacityUnits',
                'ConsumedWriteCapacityUnits',
                'ThrottledRequests',
                'UserErrors',
                'SystemErrors'
            ]
            
            for metric_name in metric_names:
                try:
                    response = self.cloudwatch.get_metric_statistics(
                        Namespace='AWS/DynamoDB',
                        MetricName=metric_name,
                        Dimensions=[
                            {'Name': 'TableName', 'Value': self.table_name}
                        ],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=300,  # 5 minutes
                        Statistics=['Sum', 'Average']
                    )
                    
                    datapoints = response['Datapoints']
                    if datapoints:
                        latest = max(datapoints, key=lambda x: x['Timestamp'])
                        metrics[metric_name] = {
                            'sum': latest.get('Sum', 0),
                            'average': latest.get('Average', 0),
                            'timestamp': latest['Timestamp'].isoformat()
                        }
                    else:
                        metrics[metric_name] = {'sum': 0, 'average': 0}
                        
                except Exception as e:
                    logger.warning(f"Could not get metric {metric_name}: {e}")
                    metrics[metric_name] = {'error': str(e)}
            
            # Check for concerning metrics
            issues = []
            throttled_requests = metrics.get('ThrottledRequests', {}).get('sum', 0)
            user_errors = metrics.get('UserErrors', {}).get('sum', 0)
            system_errors = metrics.get('SystemErrors', {}).get('sum', 0)
            
            if throttled_requests > 0:
                issues.append(f"Throttled requests: {throttled_requests}")
            
            if user_errors > 10:
                issues.append(f"High user error rate: {user_errors}")
            
            if system_errors > 0:
                issues.append(f"System errors: {system_errors}")
            
            passed = len(issues) == 0
            message = "Capacity metrics look good" if passed else f"Issues found: {', '.join(issues)}"
            
            return {
                'passed': passed,
                'message': message,
                'details': {
                    'metrics_period': '1 hour',
                    'metrics': metrics,
                    'issues': issues
                }
            }
            
        except Exception as e:
            return {
                'passed': False,
                'message': f"Error checking capacity metrics: {str(e)}",
                'error': str(e)
            }
    
    def check_error_rates(self) -> Dict[str, Any]:
        """Check error rates and system health indicators"""
        
        try:
            # This would typically check application logs, CloudWatch logs, etc.
            # For now, we'll do a basic check of recent CloudWatch metrics
            
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=24)  # Last 24 hours
            
            try:
                # Check for system errors
                response = self.cloudwatch.get_metric_statistics(
                    Namespace='AWS/DynamoDB',
                    MetricName='SystemErrors',
                    Dimensions=[
                        {'Name': 'TableName', 'Value': self.table_name}
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=3600,  # 1 hour periods
                    Statistics=['Sum']
                )
                
                total_system_errors = sum(dp['Sum'] for dp in response['Datapoints'])
                
                # Check for user errors
                response = self.cloudwatch.get_metric_statistics(
                    Namespace='AWS/DynamoDB',
                    MetricName='UserErrors',
                    Dimensions=[
                        {'Name': 'TableName', 'Value': self.table_name}
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=3600,
                    Statistics=['Sum']
                )
                
                total_user_errors = sum(dp['Sum'] for dp in response['Datapoints'])
                
                # Define acceptable error thresholds
                system_error_threshold = 5
                user_error_threshold = 100
                
                passed = (total_system_errors <= system_error_threshold and 
                         total_user_errors <= user_error_threshold)
                
                message = f"24h errors - System: {total_system_errors}, User: {total_user_errors}"
                
                return {
                    'passed': passed,
                    'message': message,
                    'details': {
                        'period_hours': 24,
                        'system_errors': total_system_errors,
                        'user_errors': total_user_errors,
                        'system_threshold': system_error_threshold,
                        'user_threshold': user_error_threshold
                    }
                }
                
            except self.cloudwatch.exceptions.ClientError as e:
                # CloudWatch access might be limited
                return {
                    'passed': True,
                    'message': "CloudWatch metrics not accessible (permissions)",
                    'details': {'error': str(e)}
                }
                
        except Exception as e:
            return {
                'passed': False,
                'message': f"Error checking error rates: {str(e)}",
                'error': str(e)
            }
    
    def _check_ttl_status(self) -> bool:
        """Check if TTL is enabled on the table"""
        try:
            response = self.dynamodb.describe_time_to_live(TableName=self.table_name)
            return response['TimeToLiveDescription']['TimeToLiveStatus'] == 'ENABLED'
        except Exception:
            return False
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate a summary of all health check results"""
        
        total_checks = len(self.health_results['checks'])
        passed_checks = sum(1 for check in self.health_results['checks'].values() if check['passed'])
        failed_checks = total_checks - passed_checks
        
        critical_failures = []
        warnings = []
        
        for check_name, result in self.health_results['checks'].items():
            if not result['passed']:
                if check_name in ['connectivity', 'table_status', 'basic_operations']:
                    critical_failures.append(check_name)
                else:
                    warnings.append(check_name)
        
        return {
            'total_checks': total_checks,
            'passed_checks': passed_checks,
            'failed_checks': failed_checks,
            'success_rate': round((passed_checks / total_checks) * 100, 1) if total_checks > 0 else 0,
            'critical_failures': critical_failures,
            'warnings': warnings,
            'recommendations': self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on health check results"""
        
        recommendations = []
        
        for check_name, result in self.health_results['checks'].items():
            if not result['passed']:
                if check_name == 'connectivity':
                    recommendations.append("Check AWS credentials and network connectivity")
                elif check_name == 'table_status':
                    recommendations.append("Ensure table is in ACTIVE state before using")
                elif check_name == 'gsi_status':
                    recommendations.append("Wait for GSIs to become active or re-run migrations")
                elif check_name == 'basic_operations':
                    recommendations.append("Check IAM permissions for DynamoDB operations")
                elif check_name == 'performance':
                    recommendations.append("Consider optimizing queries or increasing capacity")
                elif check_name == 'data_integrity':
                    recommendations.append("Review data insertion processes and validation")
                elif check_name == 'capacity_metrics':
                    recommendations.append("Monitor and adjust read/write capacity as needed")
        
        if not recommendations:
            recommendations.append("All checks passed - system is healthy")
        
        return recommendations


def main():
    """Main CLI interface for health checking"""
    
    parser = argparse.ArgumentParser(description='Echoes Database Health Checker')
    parser.add_argument('--environment', default='dev', choices=['dev', 'staging', 'prod'])
    parser.add_argument('--region', default='us-east-1')
    parser.add_argument('--quick', action='store_true', help='Run only essential checks')
    parser.add_argument('--output', choices=['text', 'json'], default='text', help='Output format')
    parser.add_argument('--output-file', help='Save results to file')
    
    args = parser.parse_args()
    
    # Initialize health checker
    try:
        checker = DatabaseHealthChecker(region=args.region, environment=args.environment)
    except Exception as e:
        logger.error(f"Failed to initialize health checker: {e}")
        return False
    
    # Run health checks
    results = checker.run_all_checks(quick=args.quick)
    
    # Output results
    if args.output == 'json':
        output = json.dumps(results, indent=2, default=str)
    else:
        output = format_text_output(results)
    
    if args.output_file:
        try:
            with open(args.output_file, 'w') as f:
                f.write(output)
            logger.info(f"Results saved to {args.output_file}")
        except Exception as e:
            logger.error(f"Failed to save results: {e}")
    else:
        print(output)
    
    # Return success/failure based on overall health
    return results['overall_status'] == 'healthy'


def format_text_output(results: Dict[str, Any]) -> str:
    """Format health check results as readable text"""
    
    output = []
    output.append("=" * 60)
    output.append("ECHOES DATABASE HEALTH CHECK REPORT")
    output.append("=" * 60)
    output.append(f"Timestamp: {results['timestamp']}")
    output.append(f"Environment: {results['environment']}")
    output.append(f"Region: {results['region']}")
    output.append(f"Overall Status: {results['overall_status'].upper()}")
    output.append("")
    
    # Summary
    if 'summary' in results:
        summary = results['summary']
        output.append("SUMMARY:")
        output.append(f"  Total Checks: {summary['total_checks']}")
        output.append(f"  Passed: {summary['passed_checks']}")
        output.append(f"  Failed: {summary['failed_checks']}")
        output.append(f"  Success Rate: {summary['success_rate']}%")
        output.append("")
    
    # Individual check results
    output.append("CHECK RESULTS:")
    for check_name, result in results['checks'].items():
        status = "✓ PASS" if result['passed'] else "✗ FAIL"
        output.append(f"  {check_name}: {status}")
        output.append(f"    {result['message']}")
        
        if 'details' in result and isinstance(result['details'], dict):
            for key, value in result['details'].items():
                if isinstance(value, (str, int, float, bool)):
                    output.append(f"    {key}: {value}")
        output.append("")
    
    # Recommendations
    if 'summary' in results and 'recommendations' in results['summary']:
        output.append("RECOMMENDATIONS:")
        for rec in results['summary']['recommendations']:
            output.append(f"  • {rec}")
        output.append("")
    
    output.append("=" * 60)
    
    return "\n".join(output)


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)