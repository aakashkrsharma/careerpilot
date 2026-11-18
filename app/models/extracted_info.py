"""
Pydantic models for Extracted Information data validation
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ExtractedInfoBase(BaseModel):
    """Base model for extracted information"""
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    summary: Optional[str] = None
    experience: Optional[str] = None
    skills: Optional[str] = None
    education: Optional[str] = None

class ExtractedInfoCreate(ExtractedInfoBase):
    """Model for creating extracted information"""
    candidate_id: int
    resume_id: int

class ExtractedInfoUpdate(ExtractedInfoBase):
    """Model for updating extracted information"""
    pass

class ExtractedInfo(ExtractedInfoBase):
    """Model for returning extracted information"""
    id: int
    candidate_id: int
    resume_id: int
    is_approved: bool = False
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class ExtractedInfoList(BaseModel):
    """Model for listing extracted info"""
    extracted_info_list: List[ExtractedInfo]
    total: int