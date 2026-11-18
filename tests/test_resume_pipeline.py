import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from docx import Document
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models import Base, ExtractedInfo, Resume


class ResumePipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_cwd = Path.cwd()
        os.chdir(self.temp_dir.name)

        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

        from app.services.candidate_service import CandidateService
        from app.services.extraction_service import ExtractionService
        from app.services.llm_service import LLMService
        from app.services.resume_service import ResumeService

        self.candidate_service = CandidateService()
        self.extraction_service = ExtractionService()
        self.llm_service = LLMService()
        self.resume_service = ResumeService()

        self.db_patches = [
            patch("app.services.candidate_service.get_db", self.get_db),
            patch("app.services.resume_service.get_db", self.get_db),
            patch(
                "app.services.extraction_service.SessionLocal",
                self.session_factory,
            ),
        ]
        for db_patch in self.db_patches:
            db_patch.start()

    def tearDown(self):
        for db_patch in self.db_patches:
            db_patch.stop()
        self.engine.dispose()
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def get_db(self):
        db = self.session_factory()
        try:
            yield db
        finally:
            db.close()

    def create_candidate_and_resume(self):
        candidate = self.candidate_service.create_candidate(
            full_name="Existing Candidate",
            email="existing@example.com",
        )
        file_path = self.resume_service.save_resume_file(
            "resume.txt",
            b"Resume contents for extraction.",
        )
        text = self.resume_service.extract_text_from_file(file_path)
        resume = self.resume_service.create_resume_record(
            candidate_id=candidate.id,
            file_name="resume.txt",
            file_path=file_path,
            extracted_text=text,
        )
        return candidate, resume

    def extract(self, candidate_id, resume_id):
        extracted_data = {
            "full_name": "Reviewed Candidate",
            "email": "reviewed@example.com",
            "phone": "555-0100",
            "location": "Toronto",
            "linkedin": "https://linkedin.com/in/candidate",
            "github": None,
            "summary": "Experienced engineer",
            "experience": "Five years of experience",
            "skills": "Python, SQL",
            "education": "BSc Computer Science",
        }
        raw_response = json.dumps(extracted_data)
        with patch.object(self.llm_service, "_get_llm_response", return_value=raw_response):
            result = self.llm_service.extract_information_from_resume(
                "Resume text",
                candidate_id,
                resume_id,
            )
        return result

    @staticmethod
    def create_pdf_with_text(text):
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]
        stream = (
            b"BT /F1 12 Tf 20 100 Td ("
            + text.encode("ascii")
            + b") Tj ET"
        )
        objects.append(
            b"<< /Length "
            + str(len(stream)).encode()
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )

        pdf = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for number, body in enumerate(objects, 1):
            offsets.append(len(pdf))
            pdf.extend(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")

        xref_offset = len(pdf)
        pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode())
        pdf.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            pdf.extend(f"{offset:010d} 00000 n \n".encode())
        pdf.extend(
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF".encode()
        )
        return bytes(pdf)

    def test_extracts_text_from_txt_and_docx_and_rejects_invalid_input(self):
        txt_path = Path("resume.txt")
        txt_path.write_text("Resume text", encoding="utf-8")
        self.assertEqual(self.resume_service.extract_text_from_file(str(txt_path)), "Resume text")

        docx_path = Path("resume.docx")
        document = Document()
        document.add_paragraph("DOCX resume text")
        document.save(docx_path)
        self.assertIn("DOCX resume text", self.resume_service.extract_text_from_file(str(docx_path)))

        with self.assertRaisesRegex(ValueError, "Unsupported resume file type"):
            self.resume_service.extract_text_from_file("resume.doc")

        empty_path = Path("empty.txt")
        empty_path.write_text("   ", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "No readable text"):
            self.resume_service.extract_text_from_file(str(empty_path))

    def test_extracts_text_from_pdf(self):
        pdf_path = Path("resume.pdf")
        pdf_path.write_bytes(self.create_pdf_with_text("PDF resume text"))

        self.assertIn("PDF resume text", self.resume_service.extract_text_from_file(str(pdf_path)))

    def test_llm_rejects_malformed_or_empty_responses_without_sample_data(self):
        with patch.object(self.llm_service, "_get_llm_response", return_value="not JSON"):
            with self.assertRaisesRegex(ValueError, "valid JSON object"):
                self.llm_service.extract_information_from_resume("Resume text", 1, 1)

        with patch.object(self.llm_service, "_get_llm_response", return_value="{}"):
            with self.assertRaisesRegex(ValueError, "no candidate information"):
                self.llm_service.extract_information_from_resume("Resume text", 1, 1)

        with self.assertRaisesRegex(ValueError, "Resume text cannot be empty"):
            self.llm_service.extract_information_from_resume("  ", 1, 1)

        with patch(
            "app.services.llm_service.ollama.generate",
            side_effect=httpx.ConnectError("Ollama is offline"),
        ):
            with self.assertRaisesRegex(ValueError, "Local Ollama extraction failed"):
                self.llm_service.extract_information_from_resume("Resume text", 1, 1)

    def test_pipeline_persists_pending_extraction_then_approved_profile(self):
        candidate, resume = self.create_candidate_and_resume()
        extraction_result = self.extract(candidate.id, resume.id)

        extraction_id = self.extraction_service.save_pending_extraction(extraction_result)
        pending = self.extraction_service.get_extraction_for_resume(candidate.id, resume.id)

        self.assertEqual(pending["id"], extraction_id)
        self.assertFalse(pending["is_reviewed"])
        self.assertFalse(pending["is_approved"])
        self.assertEqual(pending["prompt_used"], extraction_result["prompt_used"])
        self.assertEqual(pending["llm_response"], extraction_result["llm_response"])
        self.assertTrue(pending["full_name"])
        candidate_extractions = self.candidate_service.get_candidate_extracted_info(
            candidate.id
        )
        self.assertEqual(len(candidate_extractions), 1)
        self.assertEqual(candidate_extractions[0].id, extraction_id)

        with self.session_factory() as db:
            stored_resume = db.get(Resume, resume.id)
            self.assertTrue(stored_resume.is_processed)

        updated_fields = dict(pending)
        updated_fields["full_name"] = "Corrected Candidate"
        self.extraction_service.save_review(
            extraction_id=extraction_id,
            candidate_id=candidate.id,
            updated_fields=updated_fields,
            is_approved=True,
        )

        saved = self.extraction_service.get_extraction_for_resume(candidate.id, resume.id)
        updated_candidate = self.candidate_service.get_candidate_by_id(candidate.id)

        self.assertTrue(saved["is_reviewed"])
        self.assertTrue(saved["is_approved"])
        self.assertIsNotNone(saved["reviewed_at"])
        self.assertIsNotNone(saved["approved_at"])
        self.assertEqual(saved["full_name"], "Corrected Candidate")
        self.assertEqual(updated_candidate.full_name, "Existing Candidate")
        self.assertEqual(updated_candidate.email, "existing@example.com")
        self.assertEqual(updated_candidate.phone, "555-0100")

    def test_existing_profile_values_change_only_with_explicit_replace_approval(self):
        candidate, resume = self.create_candidate_and_resume()
        extraction_id = self.extraction_service.save_pending_extraction(
            self.extract(candidate.id, resume.id)
        )
        pending = self.extraction_service.get_extraction_for_resume(candidate.id, resume.id)

        self.extraction_service.save_review(
            extraction_id=extraction_id,
            candidate_id=candidate.id,
            updated_fields=pending,
            is_approved=True,
            replace_existing=True,
        )

        updated_candidate = self.candidate_service.get_candidate_by_id(candidate.id)
        self.assertEqual(updated_candidate.full_name, "Reviewed Candidate")
        self.assertEqual(updated_candidate.email, "reviewed@example.com")

    def test_unapproved_or_mismatched_extraction_cannot_update_candidate(self):
        candidate, resume = self.create_candidate_and_resume()
        extraction_id = self.extraction_service.save_pending_extraction(
            self.extract(candidate.id, resume.id)
        )
        pending = self.extraction_service.get_extraction_for_resume(candidate.id, resume.id)
        pending["full_name"] = "Unapproved Change"

        self.extraction_service.save_review(
            extraction_id=extraction_id,
            candidate_id=candidate.id,
            updated_fields=pending,
            is_approved=False,
            replace_existing=True,
        )
        self.assertEqual(
            self.candidate_service.get_candidate_by_id(candidate.id).full_name,
            "Existing Candidate",
        )

        with self.assertRaisesRegex(ValueError, "not found for this candidate"):
            self.extraction_service.save_review(
                extraction_id=extraction_id,
                candidate_id=candidate.id + 1,
                updated_fields=pending,
                is_approved=True,
                replace_existing=True,
            )

        mismatched_result = self.extract(candidate.id + 1, resume.id)
        with self.assertRaisesRegex(ValueError, "not found for the selected candidate"):
            self.extraction_service.save_pending_extraction(mismatched_result)

    def test_duplicate_email_replacement_rolls_back_review_and_profile(self):
        candidate, resume = self.create_candidate_and_resume()
        self.candidate_service.create_candidate(
            full_name="Another Candidate",
            email="reviewed@example.com",
        )
        extraction_id = self.extraction_service.save_pending_extraction(
            self.extract(candidate.id, resume.id)
        )
        pending = self.extraction_service.get_extraction_for_resume(candidate.id, resume.id)

        with self.assertRaisesRegex(ValueError, "candidate email addresses must be unique"):
            self.extraction_service.save_review(
                extraction_id=extraction_id,
                candidate_id=candidate.id,
                updated_fields=pending,
                is_approved=True,
                replace_existing=True,
            )

        saved = self.extraction_service.get_extraction_for_resume(candidate.id, resume.id)
        updated_candidate = self.candidate_service.get_candidate_by_id(candidate.id)
        self.assertFalse(saved["is_reviewed"])
        self.assertFalse(saved["is_approved"])
        self.assertEqual(updated_candidate.email, "existing@example.com")

    def test_failed_or_malformed_extraction_is_not_persisted(self):
        candidate, resume = self.create_candidate_and_resume()
        result = {
            "candidate_id": candidate.id,
            "resume_id": resume.id,
            "extracted_data": {},
            "prompt_used": "prompt",
            "llm_response": "invalid",
        }

        with self.assertRaisesRegex(ValueError, "no candidate information"):
            self.extraction_service.save_pending_extraction(result)

        with self.session_factory() as db:
            self.assertEqual(db.query(ExtractedInfo).count(), 0)
            self.assertFalse(db.get(Resume, resume.id).is_processed)


if __name__ == "__main__":
    unittest.main()
