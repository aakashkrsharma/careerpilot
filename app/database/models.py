"""
Database models for CareerPilot - Local-first AI Job Hunting Agent
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import List

Base = declarative_base()

class Candidate(Base):
    """
    Model for storing candidate information
    """
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    phone = Column(String)
    location = Column(String)
    linkedin = Column(String)
    github = Column(String)
    summary = Column(Text)
    experience = Column(Text)
    skills = Column(Text)
    education = Column(Text)
    years_of_experience = Column(Integer)
    preferred_roles = Column(Text)
    preferred_locations = Column(Text)
    work_modes = Column(Text)
    minimum_salary = Column(Integer)
    
    # Relationship with resumes
    resumes = relationship("Resume", back_populates="candidate")
    
    # Relationship with extracted information
    extracted_info = relationship("ExtractedInfo", back_populates="candidate")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Resume(Base):
    """
    Model for storing resume information including file paths
    """
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"))
    file_name = Column(String, index=True)
    file_path = Column(String, unique=True)  # Path to original resume file
    extracted_text = Column(Text)  # Extracted text content
    is_processed = Column(Boolean, default=False)
    
    # Relationship with candidate
    candidate = relationship("Candidate", back_populates="resumes")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ExtractedInfo(Base):
    """
    Model for storing LLM-extracted information that needs human review
    """
    __tablename__ = "extracted_info"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"))
    resume_id = Column(Integer, ForeignKey("resumes.id"))
    
    # Extracted information fields
    full_name = Column(String)
    email = Column(String)
    phone = Column(String)
    location = Column(String)
    linkedin = Column(String)
    github = Column(String)
    summary = Column(Text)
    experience = Column(Text)
    skills = Column(Text)
    education = Column(Text)
    
    # Review status
    is_reviewed = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=False)
    reviewed_at = Column(DateTime)
    approved_at = Column(DateTime)
    
    # LLM interaction details
    prompt_used = Column(Text)
    llm_response = Column(Text)
    
    # Relationship with candidate and resume
    candidate = relationship("Candidate", back_populates="extracted_info")
    resume = relationship("Resume")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ExtractionHistory(Base):
    """
    Model for tracking extraction history and LLM interactions
    """
    __tablename__ = "extraction_history"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"))
    resume_id = Column(Integer, ForeignKey("resumes.id"))
    
    # Extraction metadata
    extraction_type = Column(String)  # e.g., 'full_resume', 'skills_only'
    prompt_used = Column(Text)
    llm_response = Column(Text)
    is_successful = Column(Boolean, default=True)
    error_message = Column(Text)
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # Relationship with candidate and resume
    candidate = relationship("Candidate")
    resume = relationship("Resume")
    
    created_at = Column(DateTime, default=datetime.utcnow)


class Job(Base):
    """Locally stored job opportunity and source metadata."""
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source", "source_job_key", name="uq_job_source_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False, default="manual", index=True)
    source_url = Column(String)
    source_job_key = Column(String, nullable=False, unique=True, index=True)
    title = Column(String, nullable=False, index=True)
    company = Column(String, nullable=False, index=True)
    location = Column(String)
    work_mode = Column(String)
    description = Column(Text)
    required_skills = Column(Text)
    minimum_experience = Column(Integer)
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    posted_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TailoredResume(Base):
    """A review-only, job-specific resume draft."""
    __tablename__ = "tailored_resumes"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"))
    draft_text = Column(Text, nullable=False)
    suggestions = Column(Text)
    limitations = Column(Text)
    prompt_used = Column(Text)
    llm_response = Column(Text)
    is_reviewed = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=False)
    exported_path = Column(String)
    reviewed_at = Column(DateTime)
    approved_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Create all tables when this module is imported
def init_db():
    """
    Initialize database tables
    """
    from .database import engine
    Base.metadata.create_all(bind=engine)