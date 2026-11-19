import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from streamlit.testing.v1 import AppTest

from app.database.models import Application, Base
from app.services.application_executor import ManualApplicationExecutor
from app.services.application_service import ApplicationService
from app.services.answer_bank_service import AnswerBankService
from app.services.batch_selection_service import BatchSelectionService
from app.services.candidate_service import CandidateService
from app.services.clarification_queue_service import ClarificationQueueService
from app.services.job_service import JobService


class ApplicationWorkflowTests(unittest.TestCase):
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

        self.application_service = ApplicationService()
        self.answer_service = AnswerBankService()
        self.candidate_service = CandidateService()
        self.job_service = JobService()
        self.batch_service = BatchSelectionService(
            application_service_instance=self.application_service
        )
        self.clarification_service = ClarificationQueueService(
            answer_service=self.answer_service,
            application_service_instance=self.application_service,
        )

        self.db_patches = [
            patch("app.services.application_service.SessionLocal", self.session_factory),
            patch("app.services.answer_bank_service.SessionLocal", self.session_factory),
            patch("app.services.batch_selection_service.SessionLocal", self.session_factory),
            patch(
                "app.services.clarification_queue_service.SessionLocal",
                self.session_factory,
            ),
            patch("app.services.job_service.SessionLocal", self.session_factory),
            patch("app.services.candidate_service.get_db", self.get_db),
        ]
        for db_patch in self.db_patches:
            db_patch.start()

    def tearDown(self):
        for db_patch in reversed(self.db_patches):
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

    def create_candidate(self, **kwargs):
        defaults = {
            "full_name": "Workflow Candidate",
            "email": "workflow@example.com",
        }
        defaults.update(kwargs)
        return self.candidate_service.create_candidate(**defaults)

    def create_job(self, title="Backend Engineer", company="Example Labs", **kwargs):
        source_url = kwargs.pop(
            "source_url",
            f"https://jobs.example.test/{len(self.job_service.get_jobs()) + 1}",
        )
        kwargs.setdefault("required_skills", "Python")
        return self.job_service.create_job(
            title=title,
            company=company,
            source_url=source_url,
            **kwargs,
        )

    def mark_applied(self, application_id, candidate_id, applied_at=None):
        with self.session_factory() as db:
            application = db.query(Application).filter(
                Application.id == application_id
            ).one()
            status = application.status
        if status != "applied":
            self.application_service.transition_status(
                application_id,
                candidate_id,
                "ready",
                reason="Candidate reviewed the application.",
            )
            self.application_service.transition_status(
                application_id,
                candidate_id,
                "submitted",
                reason="Manual submission completed.",
            )
            self.application_service.transition_status(
                application_id,
                candidate_id,
                "applied",
                reason="Candidate confirmed submission.",
                candidate_confirmed=True,
            )
        if applied_at is not None:
            with self.session_factory.begin() as db:
                application = db.query(Application).filter(
                    Application.id == application_id
                ).one()
                application.applied_at = applied_at

    def test_exact_job_reapply_is_blocked_at_day_14_and_allowed_at_day_16(self):
        candidate = self.create_candidate()
        job = self.create_job()
        first = self.application_service.create_application(
            candidate_id=candidate.id,
            job_id=job.id,
        )
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        self.mark_applied(
            first.id,
            candidate.id,
            now - timedelta(days=14),
        )

        with self.assertRaisesRegex(ValueError, "15-day reapply cooldown"):
            self.application_service.create_application(
                candidate_id=candidate.id,
                job_id=job.id,
            )

        self.mark_applied(
            first.id,
            candidate.id,
            now - timedelta(days=16),
        )
        second = self.application_service.create_application(
            candidate_id=candidate.id,
            job_id=job.id,
        )
        self.assertNotEqual(first.id, second.id)
        with self.session_factory() as db:
            self.assertEqual(
                db.query(Application).filter(
                    Application.candidate_id == candidate.id
                ).count(),
                2,
            )

    def test_same_company_different_role_is_allowed_with_zero_day_cooldown(self):
        candidate = self.create_candidate()
        first_job = self.create_job(title="Backend Engineer")
        second_job = self.create_job(
            title="Data Analyst",
            source_url="https://jobs.example.test/data-analyst",
        )
        first = self.application_service.create_application(
            candidate_id=candidate.id,
            job_id=first_job.id,
        )
        self.mark_applied(first.id, candidate.id)

        second = self.application_service.create_application(
            candidate_id=candidate.id,
            job_id=second_job.id,
        )
        self.assertEqual(second.job_id, second_job.id)

    def test_company_cooldown_can_be_configured_for_different_roles(self):
        candidate = self.create_candidate()
        first_job = self.create_job(title="Backend Engineer")
        second_job = self.create_job(
            title="Data Analyst",
            source_url="https://jobs.example.test/data-analyst",
        )
        service = ApplicationService(company_cooldown_days=1)
        first = service.create_application(
            candidate_id=candidate.id,
            job_id=first_job.id,
        )
        self.mark_applied(first.id, candidate.id)

        with self.assertRaisesRegex(ValueError, "company is within the 1-day"):
            service.create_application(
                candidate_id=candidate.id,
                job_id=second_job.id,
            )

    def test_batch_selects_twenty_jobs_in_progressive_relaxation_order(self):
        candidate = self.create_candidate(
            skills="Python",
            years_of_experience=3,
            preferred_roles="Backend Engineer",
            preferred_locations="Toronto",
            work_modes="Remote",
        )
        jobs = []
        for index in range(3):
            jobs.append(self.create_job(
                title=f"Backend Engineer {index}",
                location="Toronto",
                work_mode="Remote",
                minimum_experience=2,
            ))
        for index in range(3):
            jobs.append(self.create_job(
                title=f"Backend Developer {index}",
                location="Toronto",
                work_mode="Remote",
                minimum_experience=2,
            ))
        for index in range(3):
            jobs.append(self.create_job(
                title=f"Backend Engineer Location {index}",
                location="Montreal",
                work_mode="On-site",
                minimum_experience=2,
            ))
        for index in range(3):
            jobs.append(self.create_job(
                title=f"Backend Engineer Experience {index}",
                location="Toronto",
                work_mode="Remote",
                minimum_experience=8,
            ))
        for index in range(13):
            jobs.append(self.create_job(
                title=f"Product Manager {index}",
                location="New York",
                work_mode="On-site",
                required_skills="Kubernetes",
                minimum_experience=3,
            ))

        recently_applied = self.application_service.create_application(
            candidate_id=candidate.id,
            job_id=jobs[0].id,
        )
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        self.mark_applied(
            recently_applied.id,
            candidate.id,
            now - timedelta(days=14),
        )

        batch = self.batch_service.select_batch(
            candidate.id,
            requested_count=25,
            matching_threshold=50,
            fallback_score=20,
        )
        rows = self.batch_service.get_batch_applications(
            batch.batch_id,
            candidate.id,
        )

        self.assertEqual(batch.selected_count, 20)
        self.assertEqual(len(rows), 20)
        stages = [application.match_stage for application, _ in rows]
        self.assertEqual(
            stages,
            sorted(
                stages,
                key={
                    "strict_match": 0,
                    "adjacent_role": 1,
                    "location_work_mode": 2,
                    "experience": 3,
                    "fallback_score": 4,
                }.get,
            ),
        )
        self.assertEqual(
            set(stages),
            {
                "strict_match",
                "adjacent_role",
                "location_work_mode",
                "experience",
                "fallback_score",
            },
        )
        self.assertNotIn(jobs[0].id, {job.id for _, job in rows})
        self.assertEqual(
            [application.selected_rank for application, _ in rows],
            list(range(1, 21)),
        )
        with self.session_factory.begin() as db:
            application = db.query(Application).filter(
                Application.id == recently_applied.id
            ).one()
            application.applied_at = now - timedelta(days=16)
        next_batch = self.batch_service.select_batch(
            candidate.id,
            requested_count=20,
            matching_threshold=50,
            fallback_score=20,
        )
        next_rows = self.batch_service.get_batch_applications(
            next_batch.batch_id,
            candidate.id,
        )
        self.assertIn(jobs[0].id, {job.id for _, job in next_rows})

    def test_cancelling_draft_batch_retains_history_and_releases_active_identity(self):
        candidate = self.create_candidate()
        self.create_job()
        first_batch = self.batch_service.select_batch(
            candidate.id,
            requested_count=1,
            matching_threshold=0,
            fallback_score=0,
        )
        self.batch_service.cancel_batch(first_batch.batch_id, candidate.id)

        first_rows = self.batch_service.get_batch_applications(
            first_batch.batch_id,
            candidate.id,
        )
        self.assertEqual(len(first_rows), 1)
        self.assertEqual(first_rows[0][0].status, "cancelled")
        self.assertEqual(
            len(self.application_service.get_application_history(candidate.id)),
            1,
        )

        second_batch = self.batch_service.select_batch(
            candidate.id,
            requested_count=1,
            matching_threshold=0,
            fallback_score=0,
        )
        self.assertEqual(second_batch.selected_count, 1)
        self.assertEqual(
            len(self.application_service.get_application_history(candidate.id)),
            2,
        )

    def test_clarification_saves_approved_answers_and_reuses_them(self):
        candidate = self.create_candidate()
        first_job = self.create_job()
        first_application = self.application_service.create_application(
            candidate_id=candidate.id,
            job_id=first_job.id,
        )
        assessed = self.clarification_service.assess_questions(
            first_application.id,
            candidate.id,
            [{
                "question_text": "How long is your notice period?",
                "canonical_key": "notice_period",
            }],
        )
        self.assertEqual(len(assessed.request_ids), 1)

        self.clarification_service.resolve_request(
            assessed.request_ids[0],
            candidate.id,
            candidate_answer="30 days",
            candidate_approved=True,
            save_to_answer_bank=True,
        )
        second_job = self.create_job(
            title="Platform Engineer",
            source_url="https://jobs.example.test/platform",
        )
        second_application = self.application_service.create_application(
            candidate_id=candidate.id,
            job_id=second_job.id,
        )
        reused = self.clarification_service.assess_questions(
            second_application.id,
            candidate.id,
            [{
                "question_text": "Availability to join?",
                "canonical_key": "notice_period",
            }],
        )
        self.assertEqual(reused.auto_answers, {"notice_period": "30 days"})
        self.assertEqual(reused.request_ids, ())

    def test_high_stakes_reused_answer_still_requires_fresh_clarification(self):
        candidate = self.create_candidate()
        self.answer_service.upsert_answer(
            candidate_id=candidate.id,
            canonical_key="expected_ctc",
            answer_text="120000",
            sensitivity="high_stakes",
            is_approved=True,
        )
        job = self.create_job()
        application = self.application_service.create_application(
            candidate_id=candidate.id,
            job_id=job.id,
        )

        assessment = self.clarification_service.assess_questions(
            application.id,
            candidate.id,
            [{
                "question_text": "What is your expected CTC?",
                "canonical_key": "expected_ctc",
            }],
        )
        self.assertEqual(assessment.auto_answers, {})
        self.assertEqual(len(assessment.request_ids), 1)
        queue = self.clarification_service.get_queue(candidate.id)
        self.assertEqual(queue[0].request.sensitivity, "high_stakes")
        self.assertEqual(queue[0].request.proposed_answer, "120000")

    def test_manual_executor_requires_approval_and_never_automates_walls(self):
        candidate = self.create_candidate()
        job = self.create_job(source_url="https://jobs.example.test/login")
        application = self.application_service.create_application(
            candidate_id=candidate.id,
            job_id=job.id,
        )
        executor = ManualApplicationExecutor()
        with self.assertRaisesRegex(ValueError, "approval"):
            executor.execute(application, job, candidate_approved=False)

        result = executor.execute(application, job, candidate_approved=True)
        self.assertEqual(result.status, "manual_required")
        self.assertIn("CAPTCHA", result.manual_instructions)
        self.assertIn("Sign in directly", result.manual_instructions)

    def test_manual_handoff_and_completion_are_candidate_confirmed(self):
        candidate = self.create_candidate()
        job = self.create_job()
        application = self.application_service.create_application(
            candidate_id=candidate.id,
            job_id=job.id,
        )
        self.application_service.transition_status(
            application.id,
            candidate.id,
            "ready",
            reason="Candidate reviewed the application.",
        )

        with self.assertRaisesRegex(ValueError, "approval is required"):
            self.application_service.prepare_manual_handoff(
                application.id,
                candidate.id,
                candidate_approved=False,
                instructions="Complete the form manually.",
            )
        handoff = self.application_service.prepare_manual_handoff(
            application.id,
            candidate.id,
            candidate_approved=True,
            instructions="Complete the form manually.",
        )
        self.assertEqual(handoff.status, "manual_required")
        self.assertEqual(handoff.execution_mode, "manual")

        with self.assertRaisesRegex(ValueError, "confirmation is required"):
            self.application_service.confirm_manual_application(
                application.id,
                candidate.id,
                candidate_confirmed=False,
            )
        applied = self.application_service.confirm_manual_application(
            application.id,
            candidate.id,
            candidate_confirmed=True,
        )
        self.assertEqual(applied.status, "applied")
        self.assertIsNotNone(applied.applied_at)

    def test_applied_transition_requires_explicit_candidate_confirmation(self):
        candidate = self.create_candidate()
        job = self.create_job()
        application = self.application_service.create_application(
            candidate_id=candidate.id,
            job_id=job.id,
        )
        self.application_service.transition_status(
            application.id,
            candidate.id,
            "ready",
            reason="Candidate reviewed the application.",
        )
        self.application_service.transition_status(
            application.id,
            candidate.id,
            "submitted",
            reason="Application submitted.",
        )

        with self.assertRaisesRegex(ValueError, "Explicit candidate confirmation"):
            self.application_service.transition_status(
                application.id,
                candidate.id,
                "applied",
                reason="No confirmation provided.",
            )
        with self.assertRaisesRegex(ValueError, "Candidate confirmation is required"):
            self.application_service.confirm_application(
                application.id,
                candidate.id,
                candidate_confirmed=False,
            )
        confirmed = self.application_service.confirm_application(
            application.id,
            candidate.id,
            candidate_confirmed=True,
        )
        self.assertEqual(confirmed.status, "applied")

    def test_application_ui_pages_smoke_without_candidates(self):
        project_root = Path(__file__).resolve().parents[1]
        app_path = project_root / "app" / "main.py"
        with (
            patch("app.database.database.init_db"),
            patch(
                "app.services.candidate_service.candidate_service.get_all_candidates",
                return_value=[],
            ),
        ):
            app = AppTest.from_file(str(app_path)).run()
            self.assertEqual(app.exception, [])
            for page in (
                "Batch Review",
                "Clarification Queue",
                "Application Tracker",
                "Dashboard",
            ):
                with self.subTest(page=page):
                    app.sidebar.radio[0].set_value(page).run()
                    self.assertEqual(app.exception, [])

    def test_startup_creates_baseline_then_runs_versioned_migrations(self):
        from app.database import database

        startup_db = Path(self.temp_dir.name) / "startup.db"
        startup_engine = create_engine(f"sqlite:///{startup_db}")
        with (
            patch.object(database, "engine", startup_engine),
            patch.object(database, "DATABASE_URL", f"sqlite:///{startup_db}"),
        ):
            database.init_db()

        inspector = inspect(startup_engine)
        self.assertTrue(inspector.has_table("candidates"))
        self.assertTrue(inspector.has_table("applications"))
        self.assertTrue(inspector.has_table("alembic_version"))
        constraints = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("applications")
        }
        self.assertNotIn("uq_application_candidate_dedup", constraints)
        self.assertIn(
            "uq_application_active_candidate_dedup",
            {index["name"] for index in inspector.get_indexes("applications")},
        )
        startup_engine.dispose()


if __name__ == "__main__":
    unittest.main()
