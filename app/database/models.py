"""
Database models for CareerPilot - Local-first AI Job Hunting Agent
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
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
    salary_currency = Column(String(3))
    salary_period = Column(String(20))
    salary_text = Column(String)
    posted_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class JobSource(Base):
    """Configured connector instance and its latest health/rate-limit state."""
    __tablename__ = "job_sources"

    id = Column(Integer, primary_key=True, index=True)
    source_key = Column(String, nullable=False, unique=True, index=True)
    connector_type = Column(String, nullable=False, index=True)
    display_name = Column(String, nullable=False)
    region_group = Column(String, nullable=False, default="india")
    config_json = Column(Text, nullable=False, default="{}")
    enabled = Column(Boolean, nullable=False, default=False, index=True)
    terms_approved = Column(Boolean, nullable=False, default=False)
    priority = Column(Integer, nullable=False, default=100)
    min_interval_seconds = Column(Integer, nullable=False, default=3600)
    next_allowed_at = Column(DateTime)
    last_run_at = Column(DateTime)
    last_success_at = Column(DateTime)
    last_status = Column(String, nullable=False, default="never_run")
    last_error = Column(Text)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    last_fetched_count = Column(Integer, nullable=False, default=0)
    last_created_count = Column(Integer, nullable=False, default=0)
    last_updated_count = Column(Integer, nullable=False, default=0)
    last_duplicate_count = Column(Integer, nullable=False, default=0)
    last_cooldown_count = Column(Integer, nullable=False, default=0)
    last_excluded_region_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class JobSourceListing(Base):
    """A provider-specific listing mapped to a canonical local job."""
    __tablename__ = "job_source_listings"
    __table_args__ = (
        UniqueConstraint("source_id", "listing_key", name="uq_source_listing_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("job_sources.id"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    listing_key = Column(String, nullable=False)
    external_id = Column(String)
    source_url = Column(String)
    source_updated_at = Column(DateTime)
    first_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)


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


class ApplicationBatch(Base):
    __tablename__ = "application_batches"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    requested_count = Column(Integer, nullable=False, default=20)
    selected_count = Column(Integer, nullable=False, default=0)
    matching_threshold = Column(Integer)
    relaxation_stages = Column(Text)
    status = Column(String, nullable=False, default="draft", index=True)
    approved_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        Index(
            "uq_application_active_candidate_dedup",
            "candidate_id",
            "dedup_key",
            unique=True,
            sqlite_where=text(
                "status IN "
                "('discovered', 'tailored', 'needs_clarification', "
                "'ready', 'submitted', 'manual_required')"
            ),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    tailored_resume_id = Column(Integer, ForeignKey("tailored_resumes.id"))
    application_batch_id = Column(Integer, ForeignKey("application_batches.id"))
    dedup_key = Column(String, nullable=False, index=True)
    source = Column(String, nullable=False, default="manual", index=True)
    source_url = Column(String)
    source_external_id = Column(String)
    status = Column(String, nullable=False, default="discovered", index=True)
    execution_mode = Column(String, nullable=False, default="not_started")
    match_score = Column(Integer)
    match_stage = Column(String)
    selected_rank = Column(Integer)
    discovered_at = Column(DateTime)
    tailored_at = Column(DateTime)
    clarification_at = Column(DateTime)
    ready_at = Column(DateTime)
    submitted_at = Column(DateTime)
    applied_at = Column(DateTime)
    follow_up_at = Column(DateTime)
    external_application_id = Column(String)
    manual_instructions = Column(Text)
    notes = Column(Text)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CandidateAnswerBank(Base):
    __tablename__ = "candidate_answer_bank"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "canonical_key",
            "scope",
            "scope_value",
            name="uq_answer_bank_candidate_key_scope",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    canonical_key = Column(String, nullable=False, index=True)
    aliases = Column(Text)
    answer_text = Column(Text, nullable=False)
    scope = Column(String, nullable=False, default="global", index=True)
    scope_value = Column(String, nullable=False, default="", index=True)
    sensitivity = Column(String, nullable=False, default="normal")
    is_approved = Column(Boolean, nullable=False, default=False)
    source_application_id = Column(Integer, ForeignKey("applications.id"))
    approved_at = Column(DateTime)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ClarificationRequest(Base):
    __tablename__ = "clarification_requests"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    canonical_key = Column(String, nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    proposed_answer = Column(Text)
    candidate_answer = Column(Text)
    category = Column(String)
    sensitivity = Column(String, nullable=False, default="normal")
    save_to_answer_bank = Column(Boolean, nullable=False, default=False)
    is_resolved = Column(Boolean, nullable=False, default=False)
    resolved_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class ApplicationStatusEvent(Base):
    __tablename__ = "application_status_events"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    from_status = Column(String)
    to_status = Column(String, nullable=False)
    actor = Column(String, nullable=False, default="system")
    reason = Column(Text)
    metadata_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create all tables when this module is imported
def init_db():
    """
    Initialize database tables
    """
    from .database import engine
    Base.metadata.create_all(bind=engine)