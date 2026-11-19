import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models import Base


class ResumeTailoringTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_cwd = Path.cwd()

        import os

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
        from app.services.job_service import JobService
        from app.services.resume_service import ResumeService
        from app.services.tailoring_service import TailoringService

        self.candidate_service = CandidateService()
        self.job_service = JobService()
        self.resume_service = ResumeService()
        self.tailoring_service = TailoringService()

        self.db_patches = [
            patch(
                "app.services.candidate_service.get_db",
                self.get_db,
            ),
            patch(
                "app.services.resume_service.get_db",
                self.get_db,
            ),
            patch(
                "app.services.job_service.SessionLocal",
                self.session_factory,
            ),
            patch(
                "app.services.tailoring_service.SessionLocal",
                self.session_factory,
            ),
        ]
        for db_patch in self.db_patches:
            db_patch.start()

    def tearDown(self):
        for db_patch in reversed(self.db_patches):
            db_patch.stop()
        self.engine.dispose()

        import os

        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def get_db(self):
        db = self.session_factory()
        try:
            yield db
        finally:
            db.close()

    def create_candidate_job_and_resume(self):
        candidate = self.candidate_service.create_candidate(
            full_name="Test Candidate",
            email="test@example.com",
            skills="Python, SQL",
            experience="Built reporting tools with Python.",
            education="BSc Computer Science",
        )
        job = self.job_service.create_job(
            title="Python Developer",
            company="Example Labs",
            location="Toronto",
            work_mode="Remote",
            description="Develop APIs with Python and SQL.",
            required_skills="Python, SQL",
            minimum_experience=2,
        )
        return candidate, job

    def test_generate_draft_contains_verified_facts_only_prompt(self):
        candidate, job = self.create_candidate_job_and_resume()
        with patch.object(
            self.tailoring_service,
            "_get_llm_response",
            return_value=json.dumps({
                "draft_text": (
                    "Test Candidate\n"
                    "Skills: Python, SQL\n"
                    "Experience: Built reporting tools with Python."
                ),
                "suggestions": ["Review dates and employers."],
                "limitations": ["No salary or employer dates provided."],
            }),
        ):
            generated = self.tailoring_service.generate_draft(
                candidate.id,
                job.id,
            )

        self.assertIn("Do not add employers", generated["prompt"])
        self.assertIn("Test Candidate", generated["draft_text"])
        self.assertIn("Python", generated["draft_text"])

    def test_save_review_approval_and_export_workflow(self):
        candidate, job = self.create_candidate_job_and_resume()
        draft_id = self.tailoring_service.save_draft(
            candidate_id=candidate.id,
            job_id=job.id,
            resume_id=None,
            draft_text="Test Candidate\nSkills: Python, SQL",
            suggestions=["Keep the draft concise."],
            limitations=["No missing facts identified."],
            prompt="fact-grounded prompt",
            raw_response='{"draft_text":"Test Candidate"}',
        )

        with self.assertRaisesRegex(ValueError, "must be approved"):
            self.tailoring_service.export_draft(draft_id, candidate.id)

        draft = self.tailoring_service.review_draft(
            draft_id=draft_id,
            candidate_id=candidate.id,
            draft_text="Test Candidate\nExperience: Built reporting tools with Python.",
            suggestions="Keep verified experience.",
            limitations="No employer dates provided.",
            is_approved=True,
        )

        self.assertTrue(draft.is_reviewed)
        self.assertTrue(draft.is_approved)
        self.assertIsNotNone(draft.approved_at)

        export_path = self.tailoring_service.export_draft(
            draft_id,
            candidate.id,
        )
        exported = Path(export_path)
        self.assertTrue(exported.exists())
        self.assertIn("Built reporting tools", exported.read_text(encoding="utf-8"))

    def test_unapproved_draft_cannot_be_exported(self):
        candidate, job = self.create_candidate_job_and_resume()
        draft_id = self.tailoring_service.save_draft(
            candidate_id=candidate.id,
            job_id=job.id,
            resume_id=None,
            draft_text="Test Candidate",
            suggestions=[],
            limitations=[],
            prompt="prompt",
            raw_response="response",
        )
        self.tailoring_service.review_draft(
            draft_id=draft_id,
            candidate_id=candidate.id,
            draft_text="Test Candidate",
            suggestions="",
            limitations="",
            is_approved=False,
        )

        with self.assertRaisesRegex(ValueError, "must be approved"):
            self.tailoring_service.export_draft(draft_id, candidate.id)

    def test_malformed_or_placeholder_output_is_rejected(self):
        candidate, job = self.create_candidate_job_and_resume()
        with patch.object(
            self.tailoring_service,
            "_get_llm_response",
            return_value="not json",
        ):
            with self.assertRaisesRegex(ValueError, "valid JSON"):
                self.tailoring_service.generate_draft(candidate.id, job.id)

        with patch.object(
            self.tailoring_service,
            "_get_llm_response",
            return_value=json.dumps({
                "draft_text": "[Insert employer name]",
                "suggestions": [],
                "limitations": [],
            }),
        ):
            with self.assertRaisesRegex(ValueError, "placeholders"):
                self.tailoring_service.generate_draft(candidate.id, job.id)

    def test_candidate_and_job_must_exist_and_resume_must_be_scoped(self):
        candidate, job = self.create_candidate_job_and_resume()

        with self.assertRaisesRegex(ValueError, "Candidate was not found"):
            self.tailoring_service.generate_draft(candidate.id + 100, job.id)
        with self.assertRaisesRegex(ValueError, "Job was not found"):
            self.tailoring_service.generate_draft(candidate.id, job.id + 100)

        file_path = self.resume_service.save_resume_file(
            "resume.txt",
            b"Candidate source text",
        )
        resume = self.resume_service.create_resume_record(
            candidate_id=candidate.id,
            file_name="resume.txt",
            file_path=file_path,
            extracted_text="Candidate source text",
        )
        with patch.object(
            self.tailoring_service,
            "_get_llm_response",
            return_value=json.dumps({
                "draft_text": "Test Candidate",
                "suggestions": [],
                "limitations": [],
            }),
        ):
            generated = self.tailoring_service.generate_draft(
                candidate.id,
                job.id,
                resume.id,
            )
        self.assertIn("Candidate source text", generated["prompt"])


if __name__ == "__main__":
    unittest.main()
