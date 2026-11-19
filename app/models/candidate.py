"""
Pydantic models for Candidate data validation
"""
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class CandidateBase(BaseModel):
    """Base model for candidate information"""
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    summary: Optional[str] = None
    experience: Optional[str] = None
    skills: Optional[str] = None
    education: Optional[str] = None
    years_of_experience: Optional[int] = None
    preferred_roles: Optional[str] = None
    preferred_locations: Optional[str] = None
    work_modes: Optional[str] = None
    minimum_salary: Optional[int] = None

class CandidateCreate(CandidateBase):
    """Model for creating a new candidate"""
    pass

class CandidateUpdate(CandidateBase):
    """Model for updating candidate information"""
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None

class Candidate(CandidateBase):
    """Model for returning candidate information"""
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class CandidateList(BaseModel):
    """Model for listing candidates"""
    candidates: List[Candidate]
    total: int