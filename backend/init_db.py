"""
Database initialization script for Echoes app
"""
import os
import sys
from datetime import datetime
from sqlalchemy.exc import IntegrityError

# Add parent directory to path to import local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import engine, Base, get_db_session, create_tables, drop_tables
from models import User, Echo
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_database(drop_existing: bool = False) -> bool:
    """
    Initialize the database with tables and optional seed data
    
    Args:
        drop_existing: Whether to drop existing tables first
        
    Returns:
        bool: True if initialization successful, False otherwise
    """
    try:
        if drop_existing:
            logger.info("Dropping existing tables...")
            drop_tables()
            logger.info("Tables dropped successfully")
        
        logger.info("Creating database tables...")
        create_tables()
        logger.info("Database tables created successfully")
        
        # Verify tables were created
        if verify_tables():
            logger.info("Database initialization completed successfully")
            return True
        else:
            logger.error("Table verification failed")
            return False
            
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        return False


def verify_tables() -> bool:
    """
    Verify that all required tables exist
    
    Returns:
        bool: True if all tables exist, False otherwise
    """
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        required_tables = ['users', 'echoes']
        missing_tables = [table for table in required_tables if table not in tables]
        
        if missing_tables:
            logger.error(f"Missing tables: {missing_tables}")
            return False
        
        logger.info(f"All required tables exist: {required_tables}")
        return True
        
    except Exception as e:
        logger.error(f"Table verification failed: {str(e)}")
        return False


def create_test_user(email: str = "test@example.com", name: str = "Test User") -> str:
    """
    Create a test user for development/testing
    
    Args:
        email: User email address
        name: User name
        
    Returns:
        str: User ID if created successfully, None otherwise
    """
    try:
        db = get_db_session()
        
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            logger.info(f"Test user already exists: {email}")
            db.close()
            return existing_user.id
        
        # Create new user
        user = User(email=email, name=name)
        db.add(user)
        db.commit()
        db.refresh(user)
        
        logger.info(f"Test user created: {email} (ID: {user.id})")
        db.close()
        return user.id
        
    except IntegrityError as e:
        logger.error(f"User creation failed - integrity error: {str(e)}")
        db.rollback()
        db.close()
        return None
    except Exception as e:
        logger.error(f"Test user creation failed: {str(e)}")
        db.close()
        return None


def create_sample_echo(user_id: str) -> str:
    """
    Create a sample echo for testing
    
    Args:
        user_id: ID of the user to create echo for
        
    Returns:
        str: Echo ID if created successfully, None otherwise
    """
    try:
        db = get_db_session()
        
        # Verify user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"User not found: {user_id}")
            db.close()
            return None
        
        # Create sample echo
        echo = Echo(
            user_id=user_id,
            emotion="joy",
            caption="Sample echo for testing",
            s3_url="s3://echoes-audio-test/sample.webm",
            s3_key="sample.webm",
            location_lat=37.5407,
            location_lng=-77.4360,
            location_address="Richmond, VA, USA",
            duration=30.0,
            transcript="This is a sample echo for testing purposes",
            detected_mood="happy",
            tags='["test", "sample", "demo"]',
            file_size=1024000
        )
        
        db.add(echo)
        db.commit()
        db.refresh(echo)
        
        logger.info(f"Sample echo created: {echo.id}")
        db.close()
        return echo.id
        
    except Exception as e:
        logger.error(f"Sample echo creation failed: {str(e)}")
        db.close()
        return None


def reset_database():
    """Reset database by dropping and recreating all tables"""
    logger.info("Resetting database...")
    success = init_database(drop_existing=True)
    if success:
        logger.info("Database reset completed successfully")
    else:
        logger.error("Database reset failed")
    return success


def seed_test_data():
    """Seed database with test data"""
    logger.info("Seeding test data...")
    
    # Create test user
    user_id = create_test_user()
    if not user_id:
        logger.error("Failed to create test user")
        return False
    
    # Create sample echo
    echo_id = create_sample_echo(user_id)
    if not echo_id:
        logger.error("Failed to create sample echo")
        return False
    
    logger.info("Test data seeded successfully")
    return True


def get_database_stats():
    """Get database statistics"""
    try:
        db = get_db_session()
        
        user_count = db.query(User).count()
        echo_count = db.query(Echo).count()
        
        stats = {
            "users": user_count,
            "echoes": echo_count,
            "database_file": "echoes.db" if "sqlite" in str(engine.url) else str(engine.url)
        }
        
        db.close()
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get database stats: {str(e)}")
        return None


def main():
    """Main function for command line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Initialize Echoes database")
    parser.add_argument("--drop", action="store_true", help="Drop existing tables first")
    parser.add_argument("--seed", action="store_true", help="Seed with test data")
    parser.add_argument("--reset", action="store_true", help="Reset database completely")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    
    args = parser.parse_args()
    
    if args.stats:
        stats = get_database_stats()
        if stats:
            print("\nDatabase Statistics:")
            for key, value in stats.items():
                print(f"  {key}: {value}")
        return
    
    if args.reset:
        reset_database()
        if args.seed:
            seed_test_data()
        return
    
    # Initialize database
    success = init_database(drop_existing=args.drop)
    
    if success and args.seed:
        seed_test_data()
    
    # Show final stats
    stats = get_database_stats()
    if stats:
        print("\nDatabase Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()