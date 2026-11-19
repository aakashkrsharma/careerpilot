"""
Candidate service for CareerPilot - handles candidate profile operations
"""
from typing import Optional, List
from app.database.models import Candidate, Resume, ExtractedInfo
from app.database.database import get_db
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

class CandidateService:
    def create_candidate(self, full_name: str, email: str, **kwargs) -> Candidate:
        """
        Create a new candidate profile
        
        Args:
            full_name (str): Full name of candidate
            email (str): Email address
            **kwargs: Additional candidate information
            
        Returns:
            Candidate: Created candidate object
        """
        db = next(get_db())
        try:
            candidate = Candidate(
                full_name=full_name,
                email=email,
                **kwargs
            )
            db.add(candidate)
            db.commit()
            db.refresh(candidate)
            return candidate
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def get_candidate_by_id(self, candidate_id: int) -> Optional[Candidate]:
        """
        Get candidate by ID
        
        Args:
            candidate_id (int): Candidate ID
            
        Returns:
            Candidate or None: Candidate object if found
        """
        db = next(get_db())
        try:
            return db.query(Candidate).filter(Candidate.id == candidate_id).first()
        finally:
            db.close()
    
    def get_candidate_by_email(self, email: str) -> Optional[Candidate]:
        """
        Get candidate by email
        
        Args:
            email (str): Email address
            
        Returns:
            Candidate or None: Candidate object if found
        """
        db = next(get_db())
        try:
            return db.query(Candidate).filter(Candidate.email == email).first()
        finally:
            db.close()
    
    def get_all_candidates(self) -> List[Candidate]:
        """
        Get all candidates
        
        Returns:
            List[Candidate]: List of all candidate objects
        """
        db = next(get_db())
        try:
            return db.query(Candidate).all()
        finally:
            db.close()
    
    def update_candidate(self, candidate_id: int, **kwargs) -> Optional[Candidate]:
        """
        Update candidate information
        
        Args:
            candidate_id (int): Candidate ID
            **kwargs: Fields to update
            
        Returns:
            Candidate or None: Updated candidate object if found
        """
        allowed_fields = {
            "full_name",
            "email",
            "phone",
            "location",
            "linkedin",
            "github",
            "summary",
            "experience",
            "skills",
            "education",
            "years_of_experience",
            "preferred_roles",
            "preferred_locations",
            "work_modes",
            "minimum_salary",
        }
        if not set(kwargs).issubset(allowed_fields):
            unknown = sorted(set(kwargs) - allowed_fields)
            raise ValueError(f"Unknown candidate fields: {', '.join(unknown)}")
        if "years_of_experience" in kwargs:
            value = kwargs["years_of_experience"]
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("Years of experience must be a non-negative integer.")
        if "minimum_salary" in kwargs:
            value = kwargs["minimum_salary"]
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("Minimum salary must be a non-negative integer.")

        db = next(get_db())
        try:
            candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
            if candidate:
                for key, value in kwargs.items():
                    if hasattr(candidate, key):
                        setattr(candidate, key, value)
                db.commit()
                db.refresh(candidate)
                return candidate
            return None
        except IntegrityError as exc:
            db.rollback()
            raise ValueError(
                "The profile update conflicts with existing data; "
                "candidate email addresses must be unique."
            ) from exc
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def get_candidate_resumes(self, candidate_id: int) -> List[Resume]:
        """
        Get all resumes for a candidate
        
        Args:
            candidate_id (int): Candidate ID
            
        Returns:
            List[Resume]: List of resume objects
        """
        db = next(get_db())
        try:
            return db.query(Resume).filter(Resume.candidate_id == candidate_id).all()
        finally:
            db.close()
    
    def get_candidate_extracted_info(self, candidate_id: int) -> List[ExtractedInfo]:
        """
        Get all extracted information for a candidate
        
        Args:
            candidate_id (int): Candidate ID
            
        Returns:
            List[ExtractedInfo]: List of extracted info objects
        """
        db = next(get_db())
        try:
            return db.query(ExtractedInfo).filter(ExtractedInfo.candidate_id == candidate_id).all()
        finally:
            db.close()

# Initialize service instance
candidate_service = CandidateService()