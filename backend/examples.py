#!/usr/bin/env python3
"""
Echoes Database Migration System - Usage Examples
Demonstrates common workflows and operations
"""

import os
import sys
from pathlib import Path

def print_header(title):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)

def print_command(description, command):
    """Print a formatted command example"""
    print(f"\n{description}:")
    print(f"  {command}")

def show_setup_examples():
    """Show database setup examples"""
    
    print_header("DATABASE SETUP EXAMPLES")
    
    print_command(
        "Complete setup (migrations + demo data)",
        "python backend/migrate.py setup --environment dev"
    )
    
    print_command(
        "Setup without demo data",
        "python backend/migrate.py setup --no-demo --environment dev"
    )
    
    print_command(
        "Setup with test scenarios",
        "python backend/migrate.py setup --with-test --environment dev"
    )
    
    print_command(
        "Setup for production",
        "python backend/migrate.py setup --environment prod --no-demo"
    )

def show_migration_examples():
    """Show migration management examples"""
    
    print_header("MIGRATION MANAGEMENT EXAMPLES")
    
    print_command(
        "Run all pending migrations",
        "python backend/migrations/migration_manager.py up --environment dev"
    )
    
    print_command(
        "Create new migration",
        'python backend/migrations/migration_manager.py create --description "Add user preferences"'
    )
    
    print_command(
        "Check migration status",
        "python backend/migrations/migration_manager.py status --environment dev"
    )
    
    print_command(
        "Rollback to specific version",
        "python backend/migrations/migration_manager.py down --target-version 20250101_000001 --environment dev"
    )

def show_seeding_examples():
    """Show data seeding examples"""
    
    print_header("DATA SEEDING EXAMPLES")
    
    print_command(
        "Create demo data (default: 15 users, 75 echoes each)",
        "python backend/seeds.py --action seed-demo --environment dev"
    )
    
    print_command(
        "Create custom amount of demo data",
        "python backend/seeds.py --action seed-demo --num-users 25 --echoes-per-user 100 --environment dev"
    )
    
    print_command(
        "Create test scenarios for automated testing",
        "python backend/seeds.py --action seed-test --environment dev"
    )
    
    print_command(
        "Clear all demo data (destructive!)",
        "python backend/seeds.py --action clear --confirm --environment dev"
    )

def show_health_check_examples():
    """Show health check examples"""
    
    print_header("HEALTH CHECK EXAMPLES")
    
    print_command(
        "Quick health check (essential checks only)",
        "python backend/health_check.py --environment dev --quick"
    )
    
    print_command(
        "Comprehensive health check",
        "python backend/health_check.py --environment dev"
    )
    
    print_command(
        "Save health report to JSON file",
        "python backend/health_check.py --environment dev --output json --output-file health_report.json"
    )
    
    print_command(
        "Check production environment",
        "python backend/health_check.py --environment prod --region us-west-2"
    )

def show_backup_examples():
    """Show backup and restore examples"""
    
    print_header("BACKUP & RESTORE EXAMPLES")
    
    print_command(
        "Create full backup",
        "python backend/backup_utils.py backup --bucket echoes-backups --environment dev"
    )
    
    print_command(
        "Create named backup",
        "python backend/backup_utils.py backup --bucket echoes-backups --name daily_backup_$(date +%Y%m%d) --environment dev"
    )
    
    print_command(
        "Create incremental backup",
        'python backend/backup_utils.py incremental --bucket echoes-backups --since "2025-06-27T00:00:00" --environment dev'
    )
    
    print_command(
        "List available backups",
        "python backend/backup_utils.py list --bucket echoes-backups"
    )
    
    print_command(
        "Verify backup integrity",
        "python backend/backup_utils.py verify --bucket echoes-backups --path backups/daily_backup"
    )
    
    print_command(
        "Restore from backup (dry run first)",
        "python backend/backup_utils.py restore --bucket echoes-backups --path backups/daily_backup --dry-run"
    )
    
    print_command(
        "Actual restore with overwrite",
        "python backend/backup_utils.py restore --bucket echoes-backups --path backups/daily_backup --overwrite"
    )
    
    print_command(
        "Clean up old backups",
        "python backend/backup_utils.py cleanup --bucket echoes-backups --retention-days 30"
    )

def show_workflow_examples():
    """Show common workflow examples"""
    
    print_header("COMMON WORKFLOW EXAMPLES")
    
    print("\n🚀 INITIAL PROJECT SETUP:")
    print("  1. python backend/migrate.py setup --environment dev")
    print("  2. python backend/health_check.py --environment dev --quick")
    print("  3. # Start developing with demo data!")
    
    print("\n🔄 DEVELOPMENT WORKFLOW:")
    print("  1. # Make schema changes")
    print("  2. python backend/migrations/migration_manager.py create --description 'Your change'")
    print("  3. # Edit the generated migration file")
    print("  4. python backend/migrate.py migrate --environment dev")
    print("  5. python backend/health_check.py --environment dev --quick")
    
    print("\n📊 PRODUCTION DEPLOYMENT:")
    print("  1. python backend/backup_utils.py backup --bucket prod-backups --environment prod")
    print("  2. python backend/migrate.py migrate --environment prod")
    print("  3. python backend/health_check.py --environment prod")
    print("  4. # Monitor application logs")
    
    print("\n🔧 TROUBLESHOOTING:")
    print("  1. python backend/health_check.py --environment dev --output json")
    print("  2. python backend/migrations/migration_manager.py status --environment dev")
    print("  3. # Check AWS CloudWatch logs")
    print("  4. # Rollback if needed:")
    print("     python backend/migrations/migration_manager.py down --target-version PREVIOUS_VERSION")
    
    print("\n💾 BACKUP ROUTINE:")
    print("  1. # Daily backup:")
    print("     python backend/backup_utils.py backup --bucket backups --environment prod")
    print("  2. # Weekly cleanup:")
    print("     python backend/backup_utils.py cleanup --bucket backups --retention-days 30")
    print("  3. # Monthly verification:")
    print("     python backend/backup_utils.py verify --bucket backups --path latest_backup")

def show_configuration_examples():
    """Show configuration examples"""
    
    print_header("CONFIGURATION EXAMPLES")
    
    print("\n📋 ENVIRONMENT VARIABLES:")
    print("  export AWS_REGION=us-east-1")
    print("  export AWS_PROFILE=echoes-dev")
    print("  export ECHOES_ENVIRONMENT=dev")
    print("  export ECHOES_BACKUP_BUCKET=echoes-backups-dev")
    
    print("\n🏗️ AWS SETUP REQUIREMENTS:")
    print("  # Create S3 bucket for backups")
    print("  aws s3 mb s3://echoes-backups-dev")
    print("  ")
    print("  # Ensure IAM permissions include:")
    print("  # - dynamodb:* (for table operations)")
    print("  # - s3:GetObject, s3:PutObject, s3:DeleteObject, s3:ListBucket")
    print("  # - cloudwatch:GetMetricStatistics (for health checks)")
    
    print("\n🔧 DEVELOPMENT ENVIRONMENT:")
    print("  # Install dependencies")
    print("  pip install boto3")
    print("  ")
    print("  # Configure AWS credentials")
    print("  aws configure --profile echoes-dev")
    print("  ")
    print("  # Test connection")
    print("  aws dynamodb list-tables --profile echoes-dev")

def show_integration_examples():
    """Show application integration examples"""
    
    print_header("APPLICATION INTEGRATION EXAMPLES")
    
    print("\n🔗 PYTHON APPLICATION INTEGRATION:")
    print('''
# In your application startup code
from backend.health_check import DatabaseHealthChecker

def check_database_health():
    checker = DatabaseHealthChecker(
        region=os.getenv('AWS_REGION', 'us-east-1'),
        environment=os.getenv('ECHOES_ENVIRONMENT', 'dev')
    )
    
    results = checker.run_all_checks(quick=True)
    
    if results['overall_status'] != 'healthy':
        logger.error("Database health check failed")
        # Handle gracefully - maybe use cached data or show maintenance page
        return False
    
    return True

# At application startup
if not check_database_health():
    sys.exit(1)
''')
    
    print("\n📊 MONITORING INTEGRATION:")
    print('''
# Periodic health checks (e.g., in a cron job)
*/5 * * * * cd /app && python backend/health_check.py --environment prod --output json > /tmp/health.json

# Alert on failures
python backend/health_check.py --environment prod || curl -X POST webhook-url -d "Database health check failed"
''')
    
    print("\n🔄 CI/CD INTEGRATION:")
    print('''
# In your deployment pipeline
stages:
  - name: backup
    script: python backend/backup_utils.py backup --bucket ci-backups --name pre-deploy-$(date +%s)
  
  - name: migrate
    script: python backend/migrate.py migrate --environment staging
    
  - name: health-check
    script: python backend/health_check.py --environment staging --quick
    
  - name: deploy
    # Your application deployment logic
    
  - name: post-deploy-check
    script: python backend/health_check.py --environment production
''')

def main():
    """Main function to display all examples"""
    
    print("🎯 ECHOES DATABASE MIGRATION SYSTEM")
    print("   Usage Examples and Common Workflows")
    print("   Generated on:", Path(__file__).stat().st_mtime)
    
    show_setup_examples()
    show_migration_examples()
    show_seeding_examples()
    show_health_check_examples()
    show_backup_examples()
    show_workflow_examples()
    show_configuration_examples()
    show_integration_examples()
    
    print_header("QUICK REFERENCE")
    print("\n📖 For detailed documentation, see:")
    print("   backend/migrations/README.md")
    print("\n🔧 To run system tests:")
    print("   python backend/test_migration_system.py")
    print("\n🚀 To get started quickly:")
    print("   python backend/migrate.py setup --environment dev")
    print("\n" + "=" * 60)
    print(" Ready to build amazing audio experiences! 🎵")
    print("=" * 60)

if __name__ == '__main__':
    main()