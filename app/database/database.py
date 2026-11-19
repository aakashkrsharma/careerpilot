"""
Database setup for CareerPilot - Local-first AI Job Hunting Agent
"""
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import inspect, text
import os
from pathlib import Path
from alembic import command
from alembic.config import Config

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
    _migrate_candidate_profile_columns()
    _run_alembic_migrations()


def _run_alembic_migrations():
    """Upgrade the SQLite schema to the latest repository migration."""
    project_root = Path(__file__).resolve().parents[2]
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    command.upgrade(config, "head")


def _migrate_candidate_profile_columns():
    """Add Phase 4 candidate columns to databases created by earlier versions."""
    column_definitions = {
        "experience": "TEXT",
        "skills": "TEXT",
        "education": "TEXT",
        "years_of_experience": "INTEGER",
        "preferred_roles": "TEXT",
        "preferred_locations": "TEXT",
        "work_modes": "TEXT",
        "minimum_salary": "INTEGER",
    }
    with engine.begin() as db:
        candidate_columns = {
            column["name"] for column in inspect(db).get_columns("candidates")
        }
        for column_name, column_type in column_definitions.items():
            if column_name not in candidate_columns:
                db.execute(
                    text(
                        f"ALTER TABLE candidates "
                        f"ADD COLUMN {column_name} {column_type}"
                    )
                )