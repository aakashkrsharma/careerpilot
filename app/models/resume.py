"""
Pydantic models for Resume data validation
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ResumeBase(BaseModel):
    """Base model for resume information"""
    file_name: str
    file_path: str
    extracted_text: str
    is_processed: bool = False

class ResumeCreate(ResumeBase):
    """Model for creating a new resume"""
    candidate_id: int

class ResumeUpdate(BaseModel):
    """Model for updating resume information"""
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    extracted_text: Optional[str] = None
    is_processed: Optional[bool] = None

class Resume(ResumeBase):
    """Model for returning resume information"""
    id: int
    candidate_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class ResumeList(BaseModel):
    """Model for listing resumes"""
    resumes: List[Resume]
    total: int