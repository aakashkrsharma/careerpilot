"""Pydantic model for job records."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class JobBase(BaseModel):
    title: str
    company: str
    source: str = "manual"
    source_url: Optional[str] = None
    location: Optional[str] = None
    work_mode: Optional[str] = None
    description: Optional[str] = None
    required_skills: Optional[str] = None
    minimum_experience: Optional[int] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    posted_at: Optional[datetime] = None


class JobCreate(JobBase):
    pass


class Job(JobBase):
    id: int
    source_job_key: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobMatchResult(BaseModel):
    candidate_id: int
    job_id: int
    total_score: int
    skill_score: int
    experience_score: int
    location_score: int
    work_mode_score: int
    role_score: int
    matched_skills: list[str]
    missing_skills: list[str]
    explanation: list[str]
