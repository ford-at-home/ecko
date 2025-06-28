"""
SQLAlchemy models for Echoes app
"""
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Index, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import uuid


class User(Base):
    """User model for storing user information"""
    __tablename__ = "users"
    
    # Primary key - using UUID as string for consistency with existing Cognito IDs
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # User fields as specified in requirements
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Additional fields for completeness
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active = Column(String(10), default="true")  # Using string for consistency
    
    # Relationship to echoes
    echoes = relationship("Echo", back_populates="user", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_user_email', 'email'),
        Index('idx_user_created_at', 'created_at'),
        Index('idx_user_active', 'is_active'),
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, name={self.name})>"


class Echo(Base):
    """Echo model for storing audio echoes"""
    __tablename__ = "echoes"
    
    # Primary key - using UUID as string
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Foreign key to user
    user_id = Column(String(255), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Echo fields as specified in requirements
    emotion = Column(String(50), nullable=False)
    caption = Column(Text)  # Using Text for longer captions
    s3_url = Column(String(500), nullable=False)  # S3 URLs can be long
    location_lat = Column(Float)  # Nullable for optional location
    location_lng = Column(Float)  # Nullable for optional location
    location_address = Column(String(500))  # Nullable for optional address
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    duration = Column(Float)  # Duration in seconds
    
    # Additional fields for completeness based on existing schema
    s3_key = Column(String(500))  # S3 key for file management
    file_size = Column(Integer)  # File size in bytes
    transcript = Column(Text)  # Audio transcription
    detected_mood = Column(String(50))  # AI-detected mood
    tags = Column(Text)  # JSON string of tags
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationship to user
    user = relationship("User", back_populates="echoes")
    
    # Indexes for performance - critical for queries
    __table_args__ = (
        Index('idx_echo_user_id', 'user_id'),
        Index('idx_echo_created_at', 'created_at'),
        Index('idx_echo_emotion', 'emotion'),
        Index('idx_echo_location', 'location_lat', 'location_lng'),
        Index('idx_user_created_composite', 'user_id', 'created_at'),  # Composite index for user timeline queries
        Index('idx_user_emotion_composite', 'user_id', 'emotion'),  # Composite index for emotion filtering
    )
    
    def __repr__(self):
        return f"<Echo(id={self.id}, user_id={self.user_id}, emotion={self.emotion})>"
    
    @property
    def location_dict(self):
        """Return location as dictionary if available"""
        if self.location_lat is not None and self.location_lng is not None:
            return {
                "lat": self.location_lat,
                "lng": self.location_lng,
                "address": self.location_address
            }
        return None
    
    def set_location(self, lat: float, lng: float, address: str = None):
        """Set location fields"""
        self.location_lat = lat
        self.location_lng = lng
        self.location_address = address