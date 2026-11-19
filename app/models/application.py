"""Pydantic schemas for application and answer-bank workflows."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ApplicationRecord(BaseModel):
    id: int
    candidate_id: int
    job_id: int
    tailored_resume_id: Optional[int] = None
    application_batch_id: Optional[int] = None
    dedup_key: str
    source: str
    source_url: Optional[str] = None
    source_external_id: Optional[str] = None
    status: str
    execution_mode: str
    match_score: Optional[int] = None
    match_stage: Optional[str] = None
    selected_rank: Optional[int] = None
    discovered_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None
    follow_up_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CandidateAnswer(BaseModel):
    canonical_key: str
    answer_text: str
    scope: str = "global"
    scope_value: str = ""
    sensitivity: str = "normal"
    aliases: Optional[str] = None
    is_approved: bool = True
