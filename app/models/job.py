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
