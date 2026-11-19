"""Pydantic schemas for AI-generated resume drafts."""
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TailoredResumeOutput(BaseModel):
    draft_text: str
    suggestions: list[str]
    limitations: list[str]


class TailoredResumeRecord(BaseModel):
    id: int
    candidate_id: int
    job_id: int
    resume_id: Optional[int] = None
    draft_text: str
    suggestions: Optional[str] = None
    limitations: Optional[str] = None
    is_reviewed: bool = False
    is_approved: bool = False
    exported_path: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
