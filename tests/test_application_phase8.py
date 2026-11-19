import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models import Base


class ApplicationPhase8Tests(unittest.TestCase):
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

        from app.services.answer_bank_service import AnswerBankService
        from app.services.application_service import ApplicationService
        from app.services.candidate_service import CandidateService
        from app.services.job_service import JobService

        self.answer_service = AnswerBankService()
        self.application_service = ApplicationService()
        self.candidate_service = CandidateService()
        self.job_service = JobService()

        self.db_patches = [
            patch(
                "app.services.answer_bank_service.SessionLocal",
                self.session_factory,
            ),
            patch(
                "app.services.application_service.SessionLocal",
                self.session_factory,
            ),
            patch(
                "app.services.candidate_service.get_db",
                self.get_db,
            ),
            patch(
                "app.services.job_service.SessionLocal",
                self.session_factory,
            ),
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

    def create_candidate_and_job(self):
        candidate = self.candidate_service.create_candidate(
            full_name="Application Candidate",
            email="application@example.com",
            skills="Python, SQL",
        )
        job = self.job_service.create_job(
            title="Python Developer",
            company="Example Labs",
            location="Toronto",
            source="manual",
            source_url="https://jobs.example.com/python?utm_source=mail",
            required_skills="Python, SQL",
            minimum_experience=2,
        )
        return candidate, job

    def test_answer_bank_scopes_coexist_and_resolve_in_precedence(self):
        candidate, job = self.create_candidate_and_job()

        global_ctc = self.answer_service.upsert_answer(
            candidate_id=candidate.id,
            canonical_key="Expected CTC",
            answer_text="120000",
            scope="global",
            is_approved=True,
            sensitivity="high_stakes",
        )
        company_ctc = self.answer_service.upsert_answer(
            candidate_id=candidate.id,
            canonical_key="expected_ctc",
            answer_text="125000",
            scope="company",
            scope_value="Example Labs",
            is_approved=True,
            sensitivity="high_stakes",
        )

        self.assertEqual(global_ctc.scope, "global")
        self.assertEqual(company_ctc.scope_value, "example labs")
        entries = self.answer_service.get_answers(candidate.id)
        self.assertEqual(len(entries), 2)

        resolved = self.answer_service.resolve_answer(
            candidate_id=candidate.id,
            canonical_key="expected ctc",
            scope_hints={"company": "Example Labs"},
        )
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.answer_text, "125000")

        role_resolved = self.answer_service.resolve_answer(
            candidate_id=candidate.id,
            canonical_key="expected_ctc",
            scope_hints={"role": "Python Developer"},
        )
        self.assertEqual(role_resolved.answer_text, "120000")

        self.answer_service.upsert_answer(
            candidate_id=candidate.id,
            canonical_key="notice_period",
            answer_text="30 days",
            scope="global",
            is_approved=True,
            aliases="availability to join",
        )
        alias_resolved = self.answer_service.resolve_answer(
            candidate_id=candidate.id,
            canonical_key="availability_to_join",
        )
        self.assertEqual(alias_resolved.answer_text, "30 days")

    def test_sensitive_answers_require_approval_and_aliases_reuse(self):
        candidate, _ = self.create_candidate_and_job()

        with self.assertRaisesRegex(ValueError, "explicit approval"):
            self.answer_service.upsert_answer(
                candidate_id=candidate.id,
                canonical_key="work_authorization",
                answer_text="Authorized",
                scope="global",
                sensitivity="sensitive",
                is_approved=False,
            )

        entry = self.answer_service.upsert_answer(
            candidate_id=candidate.id,
            canonical_key="notice_period",
            answer_text="30 days",
            scope="global",
            sensitivity="normal",
            is_approved=True,
            aliases="notice period, availability to join",
        )
        self.assertIn("notice period", entry.aliases)

    def test_expired_answers_are_not_resolved(self):
        candidate, _ = self.create_candidate_and_job()
        from datetime import datetime, timedelta, timezone

        self.answer_service.upsert_answer(
            candidate_id=candidate.id,
            canonical_key="current_ctc",
            answer_text="100000",
            scope="global",
            is_approved=True,
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
            - timedelta(days=1),
        )
        resolved = self.answer_service.resolve_answer(
            candidate_id=candidate.id,
            canonical_key="current ctc",
        )
        self.assertIsNone(resolved)

    def test_permanent_duplicate_prevents_repeat_across_source_and_days(self):
        candidate, job = self.create_candidate_and_job()

        first = self.application_service.create_application(
            candidate_id=candidate.id,
            job_id=job.id,
            source_external_id="external-123",
        )
        self.assertEqual(first.status, "discovered")
        self.assertIn(job.source_url.split("?")[0], first.dedup_key)

        with self.assertRaisesRegex(ValueError, "already exists"):
            self.application_service.create_application(
                candidate_id=candidate.id,
                job_id=job.id,
                source_external_id="different-external-id",
            )

        with self.session_factory() as db:
            count = db.query(__import__(
                "app.database.models",
                fromlist=["Application"],
            ).Application).filter(
                __import__(
                    "app.database.models",
                    fromlist=["Application"],
                ).Application.candidate_id == candidate.id
            ).count()
            self.assertEqual(count, 1)

    def test_manual_and_url_job_representations_prevent_duplicate(self):
        candidate = self.candidate_service.create_candidate(
            full_name="Permanent Candidate",
            email="permanent@example.com",
        )
        manual_job = self.job_service.create_job(
            title="Data Engineer",
            company="Data Co",
            location="Toronto",
            source="manual",
        )
        url_job = self.job_service.create_job(
            title="data engineer",
            company="data co",
            location="Toronto",
            source="naukri",
            source_url="https://naukri.com/jobs/data-engineer",
        )

        self.application_service.create_application(
            candidate_id=candidate.id,
            job_id=manual_job.id,
        )
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.application_service.create_application(
                candidate_id=candidate.id,
                job_id=url_job.id,
            )

    def test_status_transition_records_audit_event_and_enforces_transition(self):
        candidate, job = self.create_candidate_and_job()
        application = self.application_service.create_application(
            candidate_id=candidate.id,
            job_id=job.id,
        )

        updated = self.application_service.transition_status(
            application_id=application.id,
            candidate_id=candidate.id,
            to_status="tailored",
            actor="system",
            reason="Approved tailored resume is linked.",
        )
        self.assertEqual(updated.status, "tailored")

        with self.assertRaisesRegex(ValueError, "Cannot transition"):
            self.application_service.transition_status(
                application_id=application.id,
                candidate_id=candidate.id,
                to_status="applied",
                actor="candidate",
                reason="Invalid direct transition test.",
            )

        from app.database.models import ApplicationStatusEvent

        with self.session_factory() as db:
            events = db.query(ApplicationStatusEvent).filter(
                ApplicationStatusEvent.application_id == application.id
            ).order_by(ApplicationStatusEvent.id).all()
            self.assertEqual(len(events), 2)
            self.assertEqual(events[1].from_status, "discovered")
            self.assertEqual(events[1].to_status, "tailored")

    def test_phase8_migration_creates_required_tables_and_constraints(self):
        project_root = Path(__file__).resolve().parents[1]
        migration_db = Path(self.temp_dir.name) / "phase8_migration.db"
        config = Config(str(project_root / "alembic.ini"))
        config.set_main_option(
            "sqlalchemy.url",
            f"sqlite:///{migration_db}",
        )
        command.upgrade(config, "head")

        migration_engine = create_engine(f"sqlite:///{migration_db}")
        inspector = inspect(migration_engine)
        for table_name in (
            "applications",
            "candidate_answer_bank",
            "application_batches",
            "clarification_requests",
            "application_status_events",
        ):
            self.assertTrue(inspector.has_table(table_name))

        answer_constraints = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("candidate_answer_bank")
        }
        self.assertIn(
            "uq_answer_bank_candidate_key_scope",
            answer_constraints,
        )
        migration_engine.dispose()


if __name__ == "__main__":
    unittest.main()
