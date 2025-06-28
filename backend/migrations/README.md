# Echoes Database Migration System

A comprehensive database migration and management system for the Echoes application using AWS DynamoDB.

## Overview

This migration system provides:
- **Version-controlled database migrations** with rollback support
- **Demo data seeding** with realistic test data
- **Database health monitoring** and diagnostics
- **Backup and restore utilities** with compression and incremental backups
- **Comprehensive CLI tools** for database management

## Directory Structure

```
backend/
├── migrations/
│   ├── __init__.py
│   ├── migration_manager.py       # Core migration management
│   ├── versions/                  # Migration files
│   │   ├── __init__.py
│   │   └── 20250101_000001_create_echoes_table.py
│   └── README.md                  # This file
├── seeds.py                       # Demo data generation
├── migrate.py                     # Main migration runner
├── health_check.py                # Database health monitoring
└── backup_utils.py                # Backup and restore utilities
```

## Quick Start

### 1. Complete Database Setup (Recommended)

```bash
# Set up everything: migrations + demo data
python backend/migrate.py setup --environment dev

# Set up without demo data
python backend/migrate.py setup --no-demo

# Set up with test scenarios
python backend/migrate.py setup --with-test
```

### 2. Individual Operations

```bash
# Run only migrations
python backend/migrate.py migrate --environment dev

# Seed demo data only
python backend/seeds.py --action seed-demo --environment dev

# Check migration status
python backend/migrate.py status --environment dev
```

### 3. Health Check

```bash
# Quick health check
python backend/health_check.py --environment dev --quick

# Comprehensive health check
python backend/health_check.py --environment dev

# Output to JSON file
python backend/health_check.py --environment dev --output json --output-file health_report.json
```

### 4. Backup Operations

```bash
# Create full backup
python backend/backup_utils.py backup --bucket my-backup-bucket --environment dev

# List available backups
python backend/backup_utils.py list --bucket my-backup-bucket

# Restore from backup
python backend/backup_utils.py restore --bucket my-backup-bucket --path backups/echoes_backup_dev_20250628_120000
```

## Detailed Usage

### Migration Management

The migration system uses a version-based approach with automatic tracking:

#### Creating New Migrations

```bash
# Create a new migration file
python backend/migrations/migration_manager.py create --description "Add user preferences table"
```

This creates a new migration file in `versions/` with a timestamp-based version number.

#### Running Migrations

```bash
# Apply all pending migrations
python backend/migrations/migration_manager.py up --environment dev

# Apply migrations up to specific version
python backend/migrations/migration_manager.py up --target-version 20250101_000002 --environment dev

# Rollback to specific version
python backend/migrations/migration_manager.py down --target-version 20250101_000001 --environment dev

# Check migration status
python backend/migrations/migration_manager.py status --environment dev
```

### Demo Data Seeding

The seeding system creates realistic demo data for development and testing:

#### Demo Data Features

- **15 demo users** with varied profiles and preferences
- **75 echoes per user** (1,125 total by default) distributed over the past year
- **Realistic locations** including parks, beaches, landmarks, and urban areas
- **Varied emotions** and mood patterns
- **Rich metadata** including location data, tags, and audio metadata
- **Test scenarios** for automated testing

#### Seeding Commands

```bash
# Create demo data (default: 15 users, 75 echoes each)
python backend/seeds.py --action seed-demo --environment dev

# Custom amounts
python backend/seeds.py --action seed-demo --num-users 25 --echoes-per-user 100 --environment dev

# Create test scenarios for automated testing
python backend/seeds.py --action seed-test --environment dev

# Clear all demo data (destructive!)
python backend/seeds.py --action clear --confirm --environment dev
```

#### Demo User Profiles

The system creates users with realistic profiles:

- `alex_music_lover` - Focuses on music and concert experiences
- `sarah_nature_girl` - Prefers outdoor and nature locations
- `mike_city_explorer` - Urban experiences and city exploration
- `luna_dreamer` - Contemplative and peaceful moments
- And 11 more diverse user types...

### Health Monitoring

Comprehensive health checking system:

#### Health Check Categories

1. **Connectivity** - AWS credentials and DynamoDB access
2. **Table Status** - Table and GSI status validation
3. **Basic Operations** - CRUD operation testing
4. **Migration Status** - Applied migrations verification
5. **Performance** - Query response time monitoring
6. **Data Integrity** - Data format and consistency checks
7. **Capacity Metrics** - CloudWatch metrics analysis
8. **Error Rates** - System and user error monitoring

#### Health Check Commands

```bash
# Quick essential checks only
python backend/health_check.py --environment dev --quick

# Full comprehensive health check
python backend/health_check.py --environment dev

# Save detailed report
python backend/health_check.py --environment dev --output json --output-file health_$(date +%Y%m%d).json

# Monitor specific environment
python backend/health_check.py --environment prod --region us-west-2
```

### Backup and Restore

Advanced backup system with compression and incremental backups:

#### Backup Features

- **Full backups** with manifest-based multi-file support
- **Incremental backups** for changed data only
- **Compression** using gzip for space efficiency
- **Parallel processing** for large datasets
- **Verification** of backup integrity
- **Retention policies** with automatic cleanup
- **Metadata preservation** including table structure

#### Backup Commands

```bash
# Create full backup
python backend/backup_utils.py backup --bucket echoes-backups --environment dev --name daily_backup

# Create incremental backup since last backup
python backend/backup_utils.py incremental --bucket echoes-backups --since 2025-06-27T00:00:00 --environment dev

# List all available backups
python backend/backup_utils.py list --bucket echoes-backups

# Verify backup integrity
python backend/backup_utils.py verify --bucket echoes-backups --path backups/daily_backup

# Restore from backup (with dry run first)
python backend/backup_utils.py restore --bucket echoes-backups --path backups/daily_backup --dry-run

# Actual restore
python backend/backup_utils.py restore --bucket echoes-backups --path backups/daily_backup --overwrite

# Clean up old backups (keep last 30 days, 4 weekly, 12 monthly)
python backend/backup_utils.py cleanup --bucket echoes-backups --retention-days 30
```

## Database Schema

### Main Table: EchoesTable

```
Partition Key: userId (String)
Sort Key: timestamp (String - ISO 8601)

Attributes:
- echoId (String) - Unique identifier for direct access
- emotion (String) - User-selected emotion
- s3Url (String) - Audio file location
- location (Map) - Lat/lng coordinates and metadata
- tags (List) - Flexible tagging system
- transcript (String) - Audio transcription
- detectedMood (String) - AI-detected mood
- metadata (Map) - Audio format, duration, quality scores
- version (Number) - For optimistic locking
- ttl (Number) - Time-to-live for automatic expiration
```

### Global Secondary Indexes

1. **emotion-timestamp-index**: Query by emotion across all users
2. **echoId-index**: Direct access by echo ID for sharing
3. **userId-emotion-index**: User's echoes filtered by emotion

### Migration Tracking Table: EchoesMigrations

```
Partition Key: version (String)

Attributes:
- description (String) - Migration description
- applied_at (String) - When migration was applied
- status (String) - Migration status
- environment (String) - Target environment
```

## Environment Configuration

The system supports multiple environments with proper isolation:

### Development Environment
- Table: `EchoesTable-dev`
- Migration Table: `EchoesMigrations-dev`
- Demo data enabled
- Comprehensive logging

### Staging Environment
- Table: `EchoesTable-staging`
- Migration Table: `EchoesMigrations-staging`
- Production-like data
- Performance monitoring

### Production Environment
- Table: `EchoesTable-prod`
- Migration Table: `EchoesMigrations-prod`
- No demo data
- Full monitoring and alerting

## Best Practices

### Migration Best Practices

1. **Always test migrations** in development first
2. **Use descriptive migration names** that explain the change
3. **Implement rollback logic** for all migrations
4. **Keep migrations idempotent** - safe to run multiple times
5. **Backup before major migrations** in production

### Seeding Best Practices

1. **Use realistic data** that matches production patterns
2. **Include edge cases** in test scenarios
3. **Regularly refresh demo data** to match current schema
4. **Document special test users** and their purposes

### Health Check Best Practices

1. **Run health checks** before and after deployments
2. **Monitor performance trends** over time
3. **Set up automated alerts** for critical failures
4. **Document baseline performance** metrics

### Backup Best Practices

1. **Schedule regular backups** (daily for production)
2. **Test restore procedures** regularly
3. **Monitor backup sizes** and performance
4. **Keep multiple backup generations** for safety
5. **Store backups in different regions** for disaster recovery

## Troubleshooting

### Common Issues

#### Migration Failures

```bash
# Check migration status
python backend/migrate.py status --environment dev

# View detailed logs
python backend/migrate.py migrate --environment dev 2>&1 | tee migration.log

# Rollback if needed
python backend/migrations/migration_manager.py down --target-version previous_version --environment dev
```

#### Health Check Failures

```bash
# Run detailed health check
python backend/health_check.py --environment dev --output json

# Check specific connectivity
aws dynamodb list-tables --region us-east-1

# Verify table status
aws dynamodb describe-table --table-name EchoesTable-dev --region us-east-1
```

#### Backup Issues

```bash
# Verify backup integrity
python backend/backup_utils.py verify --bucket your-bucket --path backup-path

# Check S3 permissions
aws s3 ls s3://your-backup-bucket/

# Test restore with dry run
python backend/backup_utils.py restore --bucket your-bucket --path backup-path --dry-run
```

### Performance Issues

1. **Query Performance**: Check GSI usage and key distribution
2. **Large Scans**: Use parallel scanning for large datasets
3. **Write Throttling**: Monitor capacity metrics and adjust billing mode
4. **Memory Usage**: Tune batch sizes for large operations

### Permission Issues

Ensure your AWS credentials have the following permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:*",
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket",
                "cloudwatch:GetMetricStatistics"
            ],
            "Resource": "*"
        }
    ]
}
```

## Integration with Application

### Environment Variables

Set these environment variables in your application:

```bash
export AWS_REGION=us-east-1
export ECHOES_ENVIRONMENT=dev
export ECHOES_TABLE_NAME=EchoesTable-dev
export ECHOES_MIGRATION_TABLE=EchoesMigrations-dev
```

### Application Integration

```python
# In your application code
from backend.health_check import DatabaseHealthChecker

# Check database health before starting application
health_checker = DatabaseHealthChecker(region='us-east-1', environment='dev')
health_results = health_checker.run_all_checks(quick=True)

if health_results['overall_status'] != 'healthy':
    logger.error("Database health check failed")
    # Handle accordingly
```

## Monitoring and Alerting

### CloudWatch Integration

The health check system integrates with CloudWatch to monitor:

- Read/Write capacity consumption
- Throttling events
- Error rates
- Query performance

### Recommended Alerts

1. **High Error Rate**: > 1% of requests failing
2. **Throttling**: Any throttled requests
3. **High Latency**: Query times > 100ms
4. **Low Capacity**: Approaching provisioned limits

## Contributing

### Adding New Migrations

1. Create migration file using the manager
2. Implement both `up()` and `down()` methods
3. Test thoroughly in development
4. Document any breaking changes

### Extending Health Checks

1. Add new check method to `DatabaseHealthChecker`
2. Include in `run_all_checks()` method
3. Add appropriate error handling
4. Update documentation

### Improving Demo Data

1. Add new user types or scenarios
2. Include more realistic data patterns
3. Add edge cases for testing
4. Update seed reports

---

For additional support or questions, refer to the main project documentation or contact the development team.