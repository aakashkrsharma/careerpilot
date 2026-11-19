import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models import Base


class JobDiscoveryTests(unittest.TestCase):
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

        from app.services.job_service import JobService

        self.job_service = JobService()
        self.db_patch = patch(
            "app.services.job_service.SessionLocal",
            self.session_factory,
        )
        self.db_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.engine.dispose()
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def test_create_job_normalizes_url_and_persists_description(self):
        job = self.job_service.create_job(
            title="Python Developer",
            company="Example Labs",
            source="naukri",
            source_url=(
                "https://Naukri.com/jobs/python/"
                "?utm_source=linkedin&position=1#details"
            ),
            location="Toronto",
            work_mode="Hybrid",
            description="Build local-first Python applications.",
            required_skills="Python, SQL",
            minimum_experience=2,
            salary_min=80000,
            salary_max=110000,
        )

        self.assertEqual(job.source, "naukri")
        self.assertEqual(
            job.source_url,
            "https://naukri.com/jobs/python?position=1",
        )
        self.assertIn("Python", job.required_skills)

    def test_tracking_parameters_and_source_variations_do_not_create_duplicate(self):
        first = self.job_service.create_job(
            title="Backend Engineer",
            company="Example Labs",
            source="indeed",
            source_url="https://jobs.example.com/role/123?utm_source=mail",
        )
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.job_service.create_job(
                title="Backend Engineer",
                company="Example Labs",
                source="manual",
                source_url="https://jobs.example.com/role/123",
            )
        self.assertEqual(first.source_job_key, "https://jobs.example.com/role/123")

    def test_manual_jobs_without_urls_are_deduplicated(self):
        first = self.job_service.create_job(
            title="Data Engineer",
            company="Data Co",
            location="Toronto",
        )
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.job_service.create_job(
                title="  data engineer ",
                company="data co",
                location="Toronto",
            )
        self.assertEqual(len(self.job_service.get_jobs()), 1)
        self.assertTrue(first.source_job_key)

    def test_filter_jobs_by_title_location_work_mode_skills_and_experience(self):
        self.job_service.create_job(
            title="Senior Python Developer",
            company="Example Labs",
            location="Toronto",
            work_mode="Remote",
            required_skills="Python, SQL",
            minimum_experience=5,
        )
        self.job_service.create_job(
            title="Junior Python Developer",
            company="Example Labs",
            location="Ottawa",
            work_mode="Hybrid",
            required_skills="Python",
            minimum_experience=1,
        )

        jobs = self.job_service.filter_jobs(
            title_or_company="Python",
            location="Toronto",
            work_mode="Remote",
            required_skills="Python, SQL",
            maximum_experience=6,
        )
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Senior Python Developer")

        junior_jobs = self.job_service.filter_jobs(
            location="Ottawa",
            maximum_experience=2,
        )
        self.assertEqual(len(junior_jobs), 1)
        self.assertEqual(junior_jobs[0].title, "Junior Python Developer")

    def test_invalid_job_fields_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Job title is required"):
            self.job_service.create_job(title=" ", company="Example")
        with self.assertRaisesRegex(ValueError, "complete http or https"):
            self.job_service.create_job(
                title="Developer",
                company="Example",
                source_url="example.com/job",
            )
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            self.job_service.create_job(
                title="Developer",
                company="Example",
                salary_min=100000,
                salary_max=90000,
            )


if __name__ == "__main__":
    unittest.main()
