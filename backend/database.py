"""
Database configuration and session management for Echoes app
"""
import os
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine
import sqlite3

# Database URL - defaults to local SQLite file
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./echoes.db")

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=os.getenv("DEBUG", "false").lower() == "true"  # Enable SQL logging in debug mode
)

# Enable foreign key constraints for SQLite
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key constraints for SQLite"""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session
    
    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)

def drop_tables():
    """Drop all database tables"""
    Base.metadata.drop_all(bind=engine)

def get_db_session() -> Session:
    """
    Get a database session for non-dependency injection usage
    
    Returns:
        Session: SQLAlchemy database session
    """
    return SessionLocal()