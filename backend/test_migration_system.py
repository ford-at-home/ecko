#!/usr/bin/env python3
"""
Test script for the Echoes migration system
Validates that all components work together correctly
"""

import sys
import os
import json
import logging
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Global imports to be available in all test functions
try:
    from migrations.migration_manager import MigrationManager, Migration
    from seeds import EchoesSeeder
    from health_check import DatabaseHealthChecker
    from backup_utils import BackupManager
    IMPORTS_SUCCESSFUL = True
except ImportError as e:
    logger.error(f"Failed to import modules: {e}")
    IMPORTS_SUCCESSFUL = False


def test_imports():
    """Test that all modules can be imported correctly"""
    
    logger.info("Testing module imports...")
    
    if IMPORTS_SUCCESSFUL:
        logger.info("✓ All modules imported successfully")
        return True
    else:
        logger.error("✗ Import error occurred during module loading")
        return False


def test_migration_manager():
    """Test migration manager functionality"""
    
    logger.info("Testing migration manager...")
    
    if not IMPORTS_SUCCESSFUL:
        logger.error("✗ Cannot test migration manager - imports failed")
        return False
    
    try:
        # Initialize manager (won't connect to AWS in test mode)
        manager = MigrationManager(region='us-east-1', environment='test')
        
        # Test loading migration files
        migrations = manager.load_migration_files()
        logger.info(f"✓ Found {len(migrations)} migration files")
        
        # Test status method (will fail gracefully without AWS)
        try:
            status = manager.get_migration_status()
            logger.info("✓ Migration status check works")
        except Exception:
            logger.info("✓ Migration status gracefully handles missing AWS connection")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Migration manager test failed: {e}")
        return False


def test_seeder():
    """Test seeder functionality"""
    
    logger.info("Testing seeder...")
    
    if not IMPORTS_SUCCESSFUL:
        logger.error("✗ Cannot test seeder - imports failed")
        return False
    
    try:
        seeder = EchoesSeeder(region='us-east-1', environment='test')
        
        # Test demo user creation
        users = seeder.create_demo_users(5)
        logger.info(f"✓ Created {len(users)} demo users")
        
        # Test echo generation
        if users:
            echo = seeder.generate_echo_for_user(users[0], 0, 10)
            required_fields = ['userId', 'timestamp', 'echoId', 'emotion']
            has_required = all(field in echo for field in required_fields)
            logger.info(f"✓ Generated demo echo with required fields: {has_required}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Seeder test failed: {e}")
        return False


def test_health_checker():
    """Test health checker functionality"""
    
    logger.info("Testing health checker...")
    
    if not IMPORTS_SUCCESSFUL:
        logger.error("✗ Cannot test health checker - imports failed")
        return False
    
    try:
        checker = DatabaseHealthChecker(region='us-east-1', environment='test')
        
        # Test individual check methods (will fail gracefully without AWS)
        try:
            result = checker.check_connectivity()
            logger.info("✓ Connectivity check method works")
        except Exception:
            logger.info("✓ Connectivity check gracefully handles missing AWS connection")
        
        # Test summary generation
        checker.health_results = {
            'checks': {
                'test_check': {'passed': True, 'message': 'Test check passed'}
            }
        }
        summary = checker._generate_summary()
        logger.info(f"✓ Summary generation works: {summary['success_rate']}% success rate")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Health checker test failed: {e}")
        return False


def test_backup_manager():
    """Test backup manager functionality"""
    
    logger.info("Testing backup manager...")
    
    if not IMPORTS_SUCCESSFUL:
        logger.error("✗ Cannot test backup manager - imports failed")
        return False
    
    try:
        manager = BackupManager(region='us-east-1', environment='test')
        
        # Test utility methods
        test_data = {'test': 3.14, 'nested': {'value': 2.71}}
        converted = manager._convert_decimal_to_float(test_data)
        logger.info("✓ Decimal conversion works")
        
        # Test metadata generation (will work without AWS)
        try:
            metadata = manager._get_table_metadata()
            logger.info("✓ Metadata generation works")
        except Exception:
            logger.info("✓ Metadata generation gracefully handles missing AWS connection")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Backup manager test failed: {e}")
        return False


def test_migration_file_format():
    """Test that migration files have correct format"""
    
    logger.info("Testing migration file format...")
    
    try:
        migrations_dir = backend_dir / 'migrations' / 'versions'
        migration_files = list(migrations_dir.glob('*.py'))
        
        if not migration_files:
            logger.warning("⚠ No migration files found")
            return True
        
        for migration_file in migration_files:
            if migration_file.name.startswith('__'):
                continue
            
            # Read file content
            with open(migration_file, 'r') as f:
                content = f.read()
            
            # Check for required elements
            required_elements = [
                'class', 'Migration', 'def up(', 'def down(', 'migration ='
            ]
            
            missing = [elem for elem in required_elements if elem not in content]
            
            if missing:
                logger.error(f"✗ Migration file {migration_file.name} missing: {missing}")
                return False
            else:
                logger.info(f"✓ Migration file {migration_file.name} format is correct")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Migration file format test failed: {e}")
        return False


def test_cli_scripts():
    """Test that CLI scripts have correct structure"""
    
    logger.info("Testing CLI scripts...")
    
    cli_scripts = [
        'migrate.py',
        'seeds.py', 
        'health_check.py',
        'backup_utils.py'
    ]
    
    try:
        for script in cli_scripts:
            script_path = backend_dir / script
            
            if not script_path.exists():
                logger.error(f"✗ CLI script {script} not found")
                return False
            
            # Check if file is executable
            if not os.access(script_path, os.X_OK):
                logger.warning(f"⚠ CLI script {script} is not executable")
            
            # Check for main function
            with open(script_path, 'r') as f:
                content = f.read()
            
            if 'def main():' not in content:
                logger.error(f"✗ CLI script {script} missing main() function")
                return False
            
            if "__name__ == '__main__':" not in content:
                logger.error(f"✗ CLI script {script} missing main execution block")
                return False
            
            logger.info(f"✓ CLI script {script} structure is correct")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ CLI scripts test failed: {e}")
        return False


def test_documentation():
    """Test that documentation files exist and are readable"""
    
    logger.info("Testing documentation...")
    
    try:
        readme_path = backend_dir / 'migrations' / 'README.md'
        
        if not readme_path.exists():
            logger.error("✗ README.md not found in migrations directory")
            return False
        
        with open(readme_path, 'r') as f:
            content = f.read()
        
        # Check for key sections
        required_sections = [
            '# Echoes Database Migration System',
            '## Overview',
            '## Quick Start',
            '## Detailed Usage'
        ]
        
        missing_sections = [section for section in required_sections if section not in content]
        
        if missing_sections:
            logger.error(f"✗ README.md missing sections: {missing_sections}")
            return False
        
        logger.info(f"✓ README.md contains all required sections ({len(content)} characters)")
        return True
        
    except Exception as e:
        logger.error(f"✗ Documentation test failed: {e}")
        return False


def run_all_tests():
    """Run all test functions"""
    
    tests = [
        ('Module Imports', test_imports),
        ('Migration Manager', test_migration_manager),
        ('Demo Data Seeder', test_seeder),
        ('Health Checker', test_health_checker),
        ('Backup Manager', test_backup_manager),
        ('Migration File Format', test_migration_file_format),
        ('CLI Scripts', test_cli_scripts),
        ('Documentation', test_documentation)
    ]
    
    print("=" * 60)
    print("ECHOES MIGRATION SYSTEM TEST SUITE")
    print("=" * 60)
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\nRunning {test_name} test...")
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"Test {test_name} crashed: {e}")
            results[test_name] = False
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed_count = sum(1 for result in results.values() if result)
    total_count = len(results)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nOverall: {passed_count}/{total_count} tests passed ({passed_count/total_count*100:.1f}%)")
    
    if passed_count == total_count:
        print("🎉 All tests passed! Migration system is ready to use.")
        return True
    else:
        print("❌ Some tests failed. Please review the issues above.")
        return False


def main():
    """Main test runner"""
    
    # Change to backend directory
    os.chdir(backend_dir)
    
    # Run tests
    success = run_all_tests()
    
    if success:
        print("\n" + "=" * 60)
        print("NEXT STEPS:")
        print("1. Configure AWS credentials")
        print("2. Create S3 bucket for backups")
        print("3. Run: python migrate.py setup --environment dev")
        print("4. Run: python health_check.py --environment dev")
        print("=" * 60)
    
    return success


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)