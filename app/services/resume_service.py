"""
Resume service for CareerPilot - handles resume file operations and text extraction
"""
import uuid
from pathlib import Path
from typing import Optional
from zipfile import BadZipFile

from docx.opc.exceptions import PackageNotFoundError
from PyPDF2.errors import PdfReadError

from app.database.database import get_db
from app.database.models import Resume

class ResumeService:
    supported_extensions = {".pdf", ".docx", ".txt"}

    def __init__(self):
        self.data_dir = Path("data")
        self.resumes_dir = self.data_dir / "resumes"
        self.resumes_dir.mkdir(parents=True, exist_ok=True)
    
    def save_resume_file(self, file_name: str, file_content: bytes) -> str:
        """
        Save uploaded resume file to disk
        
        Args:
            file_name (str): Original filename
            file_content (bytes): File content
            
        Returns:
            str: Path to saved file
        """
        file_extension = Path(file_name).suffix.lower()
        if file_extension not in self.supported_extensions:
            raise ValueError(
                "Unsupported resume file type. Upload a PDF, DOCX, or TXT file."
            )
        if not isinstance(file_content, bytes) or not file_content:
            raise ValueError("The uploaded resume file is empty or invalid.")

        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        file_path = self.resumes_dir / unique_filename
        with open(file_path, "wb") as f:
            f.write(file_content)
            
        return str(file_path)
    
    def extract_text_from_file(self, file_path: str) -> str:
        """
        Extract text from PDF, DOCX, or TXT resume files.
        
        Args:
            file_path (str): Path to the resume file
            
        Returns:
            str: Extracted text content
        """
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in self.supported_extensions:
            raise ValueError(
                "Unsupported resume file type. Upload a PDF, DOCX, or TXT file."
            )

        try:
            if file_ext == ".pdf":
                text = self._extract_text_from_pdf(file_path)
            elif file_ext == ".docx":
                text = self._extract_text_from_docx(file_path)
            else:
                text = Path(file_path).read_text(encoding="utf-8")
        except (
            BadZipFile,
            KeyError,
            PackageNotFoundError,
            PdfReadError,
            UnicodeDecodeError,
            OSError,
            ValueError,
        ) as exc:
            raise ValueError(
                f"Could not extract readable text from the resume: {exc}"
            ) from exc

        if not text or not text.strip():
            raise ValueError("No readable text was found in the resume.")
        return text
    
    def _extract_text_from_pdf(self, file_path: str) -> str:
        """
        Extract text from PDF file
        
        Args:
            file_path (str): Path to PDF file
            
        Returns:
            str: Extracted text content
        """
        import PyPDF2

        with open(file_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            return "\n".join(page.extract_text() or "" for page in pdf_reader.pages)
    
    def _extract_text_from_docx(self, file_path: str) -> str:
        """
        Extract text from DOCX file
        
        Args:
            file_path (str): Path to DOCX file
            
        Returns:
            str: Extracted text content
        """
        from docx import Document

        doc = Document(file_path)
        return "\n".join(para.text for para in doc.paragraphs)
    
    def create_resume_record(
        self,
        candidate_id: int,
        file_name: str,
        file_path: str,
        extracted_text: str,
    ) -> Resume:
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
                is_processed=False
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