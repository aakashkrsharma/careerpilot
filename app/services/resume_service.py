"""
Resume service for CareerPilot - handles resume file operations and text extraction
"""
import os
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from app.database.models import Resume, Candidate
from app.database.database import get_db
from sqlalchemy.orm import Session

class ResumeService:
    def __init__(self):
        self.data_dir = Path("data")
        self.resumes_dir = self.data_dir / "resumes"
        self.resumes_dir.mkdir(exist_ok=True)
    
    def save_resume_file(self, file_name: str, file_content: bytes) -> str:
        """
        Save uploaded resume file to disk
        
        Args:
            file_name (str): Original filename
            file_content (bytes): File content
            
        Returns:
            str: Path to saved file
        """
        # Generate unique filename to avoid conflicts
        file_extension = os.path.splitext(file_name)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        file_path = self.resumes_dir / unique_filename
        with open(file_path, "wb") as f:
            f.write(file_content)
            
        return str(file_path)
    
    def extract_text_from_file(self, file_path: str) -> str:
        """
        Extract text from resume file (PDF/DOCX)
        
        Args:
            file_path (str): Path to the resume file
            
        Returns:
            str: Extracted text content
        """
        from pathlib import Path
        file_ext = Path(file_path).suffix.lower()
        
        try:
            if file_ext == '.pdf':
                return self._extract_text_from_pdf(file_path)
            elif file_ext in ['.docx', '.doc']:
                return self._extract_text_from_docx(file_path)
            else:
                # For other formats, try to read as text
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
        except Exception as e:
            print(f"Error extracting text from {file_path}: {e}")
            # Return empty string if extraction fails
            return ""
    
    def _extract_text_from_pdf(self, file_path: str) -> str:
        """
        Extract text from PDF file
        
        Args:
            file_path (str): Path to PDF file
            
        Returns:
            str: Extracted text content
        """
        try:
            import PyPDF2
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text()
            return text
        except ImportError:
            print("PyPDF2 not installed. Please install it to extract PDF text.")
            return ""
        except Exception as e:
            print(f"Error reading PDF: {e}")
            return ""
    
    def _extract_text_from_docx(self, file_path: str) -> str:
        """
        Extract text from DOCX file
        
        Args:
            file_path (str): Path to DOCX file
            
        Returns:
            str: Extracted text content
        """
        try:
            from docx import Document
            doc = Document(file_path)
            full_text = []
            for para in doc.paragraphs:
                full_text.append(para.text)
            return '\n'.join(full_text)
        except ImportError:
            print("python-docx not installed. Please install it to extract DOCX text.")
            return ""
        except Exception as e:
            print(f"Error reading DOCX: {e}")
            return ""
    
    def create_resume_record(self, candidate_id: int, file_name: str, file_path: str, extracted_text: str) -> Resume:
        """
        Create a resume record in the database
        
        Args:
            candidate_id (int): ID of the candidate
            file_name (str): Original filename
            file_path (str): Path to saved file
            extracted_text (str): Extracted text content
            
        Returns:
            Resume: Created resume object
        """
        db = next(get_db())
        try:
            resume = Resume(
                candidate_id=candidate_id,
                file_name=file_name,
                file_path=file_path,
                extracted_text=extracted_text,
                is_processed=True
            )
            db.add(resume)
            db.commit()
            db.refresh(resume)
            return resume
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def get_resume_by_id(self, resume_id: int) -> Optional[Resume]:
        """
        Get resume by ID
        
        Args:
            resume_id (int): Resume ID
            
        Returns:
            Resume or None: Resume object if found
        """
        db = next(get_db())
        try:
            return db.query(Resume).filter(Resume.id == resume_id).first()
        finally:
            db.close()
    
    def get_resumes_by_candidate(self, candidate_id: int) -> list:
        """
        Get all resumes for a candidate
        
        Args:
            candidate_id (int): Candidate ID
            
        Returns:
            list: List of resume objects
        """
        db = next(get_db())
        try:
            return db.query(Resume).filter(Resume.candidate_id == candidate_id).all()
        finally:
            db.close()

# Initialize service instance
resume_service = ResumeService()