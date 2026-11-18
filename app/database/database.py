"""
Database setup for CareerPilot - Local-first AI Job Hunting Agent
"""
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Create database engine
DATABASE_URL = "sqlite:///./careerpilot.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a Base class for declarative models
Base = declarative_base()

def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize the database tables
def init_db():
    """Initialize database tables"""
    from .models import Base
    Base.metadata.create_all(bind=engine)