import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import redirect_stdout

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models import (
    Application,
    Candidate,
    Job,
    JobSource,
    JobSourceListing,
    Base,
)
from app.models.workflow import (
    DiscoveryRunResult,
    JobDiscoveryCriteria,
    SourceJob,
)
from app.services.connectors import CONNECTOR_TYPES
from app.services.connectors.ats import GreenhouseConnector
from app.services.connectors.base import ConnectorError
from app.services.connectors.feeds import RSSAtomConnector, XMLFeedConnector
from app.services.connectors.public_apis import JobicyConnector
from app.services.discovery_policy import is_india_eligible
from app.services.salary_parser import parse_compensation


class MultiSourceDiscoveryTests(unittest.TestCase):
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
        self.patches = [
            patch("app.database.database.SessionLocal", self.session_factory),
            patch("app.services.job_service.SessionLocal", self.session_factory),
            patch(
                "app.services.job_source_registry_service.SessionLocal",
                self.session_factory,
            ),
            patch(
                "app.services.job_discovery_service.SessionLocal",
                self.session_factory,
            ),
            patch(
                "app.services.application_service.SessionLocal",
                self.session_factory,
            ),
        ]
        for item in self.patches:
            item.start()

        from app.services.application_service import ApplicationService
        from app.services.job_discovery_service import JobDiscoveryService
        from app.services.job_service import JobService
        from app.services.job_source_registry_service import JobSourceRegistryService

        self.jobs = JobService()
        self.registry = JobSourceRegistryService()
        self.applications = ApplicationService()
        self.candidate_id = self._create_candidate()
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.discovery = JobDiscoveryService(
            registry=self.registry,
            jobs=self.jobs,
            applications=self.applications,
            connector_factory=self._connector_factory,
            clock=lambda: self.now,
            request_interval_seconds=0,
        )
        self.connector_jobs = []
        self.connector_errors = set()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.engine.dispose()
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def _create_candidate(self):
        with self.session_factory.begin() as db:
            candidate = Candidate(full_name="Test Candidate", email="test@example.com")
            db.add(candidate)
            db.flush()
            return candidate.id

    def _register_source(self, key, *, connector_type="rss_atom", config=None):
        source = self.registry.register_source(
            source_key=key,
            connector_type=connector_type,
            display_name=key,
            region_group="india",
            config=config or {"feed_url": "https://jobs.example.com/feed.xml"},
            terms_approved=True,
            enabled=True,
        )
        return source.id

    def _connector_factory(self, source, client):
        test_case = self

        class FakeConnector:
            def __init__(self, source_key):
                self.source_key = source_key

            def discover(self, criteria):
                if self.source_key in test_case.connector_errors:
                    raise RuntimeError("fixture source failure")
                return list(test_case.connector_jobs)

        return FakeConnector(source.source_key)

    def test_upsert_deduplicates_across_providers_and_keeps_provenance(self):
        first_source_id = self._register_source("rss-first")
        second_source_id = self._register_source("rss-second")
        job = SourceJob(
            source="rss_atom",
            title="Backend Engineer",
            company="Example Labs",
            source_url="https://jobs.example.com/roles/backend?utm_source=feed",
            source_external_id="backend-1",
            location="Bengaluru, India",
        )

        first = self.jobs.upsert_normalized_job(job, source_id=first_source_id)
        second = self.jobs.upsert_normalized_job(job, source_id=second_source_id)

        self.assertTrue(first.created)
        self.assertTrue(second.matched_existing)
        self.assertEqual(first.job_id, second.job_id)
        with self.session_factory() as db:
            self.assertEqual(db.query(Job).count(), 1)
            self.assertEqual(db.query(JobSourceListing).count(), 2)
        self.assertEqual(
            {
                listing.source_name
                for listing in self.jobs.get_job_source_listings(first.job_id)
            },
            {"rss-first", "rss-second"},
        )

    def test_runner_deduplicates_repeated_listings_after_rate_limit_window(self):
        self._register_source("repeated-feed")
        self.connector_jobs = [self._eligible_job()]
        first = self.discovery.run(
            self.candidate_id,
            JobDiscoveryCriteria(query="Backend Engineer", limit=10),
        )
        self.now += timedelta(hours=2)
        second = self.discovery.run(
            self.candidate_id,
            JobDiscoveryCriteria(query="Backend Engineer", limit=10),
        )

        self.assertEqual(first.source_results[0].created_count, 1)
        self.assertEqual(second.source_results[0].duplicate_count, 1)
        with self.session_factory() as db:
            self.assertEqual(db.query(Job).count(), 1)
            self.assertEqual(db.query(JobSourceListing).count(), 1)

    def test_runner_reports_application_cooldown_without_deleting_history(self):
        source_id = self._register_source("cooldown-feed")
        existing_job = self.jobs.create_job(
            title="Backend Engineer",
            company="Example Labs",
            source="manual",
            source_url="https://jobs.example.com/roles/backend",
            location="Bengaluru, India",
        )
        application = self.applications.create_application(
            candidate_id=self.candidate_id,
            job_id=existing_job.id,
        )
        applied_at = self.now - timedelta(days=14)
        with self.session_factory.begin() as db:
            row = db.query(Application).filter(Application.id == application.id).first()
            row.status = "applied"
            row.applied_at = applied_at.replace(tzinfo=None)

        self.connector_jobs = [self._eligible_job()]
        result = self.discovery.run(
            self.candidate_id,
            JobDiscoveryCriteria(limit=10),
        )

        self.assertEqual(result.source_results[0].cooldown_count, 1)
        with self.session_factory() as db:
            self.assertEqual(db.query(Application).count(), 1)
            self.assertEqual(
                db.query(JobSourceListing)
                .filter(JobSourceListing.source_id == source_id)
                .count(),
                1,
            )

    def test_cooldown_expires_after_day_fifteen(self):
        self._register_source("expired-cooldown-feed")
        existing_job = self.jobs.create_job(
            title="Backend Engineer",
            company="Example Labs",
            source="manual",
            source_url="https://jobs.example.com/roles/backend",
            location="Bengaluru, India",
        )
        application = self.applications.create_application(
            candidate_id=self.candidate_id,
            job_id=existing_job.id,
        )
        with self.session_factory.begin() as db:
            row = db.query(Application).filter(Application.id == application.id).first()
            row.status = "applied"
            row.applied_at = (self.now - timedelta(days=16)).replace(tzinfo=None)

        self.connector_jobs = [self._eligible_job()]
        result = self.discovery.run(
            self.candidate_id,
            JobDiscoveryCriteria(limit=10),
        )

        self.assertEqual(result.source_results[0].cooldown_count, 0)
        self.assertEqual(result.source_results[0].created_count, 0)
        self.assertEqual(result.source_results[0].updated_count, 1)
        with self.session_factory() as db:
            self.assertEqual(db.query(Application).count(), 1)

    def test_rate_limit_skips_source_until_next_allowed_time(self):
        self._register_source("limited-feed")
        self.connector_jobs = [self._eligible_job()]
        self.discovery.run(self.candidate_id, JobDiscoveryCriteria(limit=10))
        limited = self.discovery.run(
            self.candidate_id,
            JobDiscoveryCriteria(limit=10),
        )

        self.assertEqual(limited.source_results[0].status, "rate_limited")

    def test_one_failed_source_does_not_interrupt_other_sources(self):
        self._register_source("failing-feed")
        self._register_source("healthy-feed")
        self.connector_errors.add("failing-feed")
        self.connector_jobs = [self._eligible_job()]

        result = self.discovery.run(
            self.candidate_id,
            JobDiscoveryCriteria(limit=10),
        )

        self.assertEqual(
            [source.status for source in result.source_results],
            ["failed", "success"],
        )
        self.assertEqual(result.source_results[1].created_count, 1)
        with self.session_factory() as db:
            failed = db.query(JobSource).filter_by(source_key="failing-feed").first()
            healthy = db.query(JobSource).filter_by(source_key="healthy-feed").first()
            self.assertEqual(failed.last_status, "failed")
            self.assertEqual(healthy.last_status, "success")

    def test_terms_must_be_approved_and_credentials_cannot_be_persisted(self):
        with self.assertRaisesRegex(ValueError, "terms"):
            self.registry.register_source(
                source_key="unapproved",
                connector_type="jobicy",
                display_name="Jobicy",
                region_group="global_remote",
                config={},
                terms_approved=False,
                enabled=True,
            )
        with self.assertRaisesRegex(ValueError, "Do not store credentials"):
            self.registry.register_source(
                source_key="credentialed",
                connector_type="rss_atom",
                display_name="Feed",
                region_group="india",
                config={
                    "feed_url": "https://jobs.example.com/feed.xml",
                    "token": "not-persisted",
                },
                terms_approved=True,
            )

    def test_source_catalog_exposes_more_than_ten_connector_types(self):
        self.assertGreaterEqual(len(CONNECTOR_TYPES), 10)
        self.assertNotIn("workday", CONNECTOR_TYPES)
        self.assertNotIn("linkedin", CONNECTOR_TYPES)
        self.assertNotIn("naukri", CONNECTOR_TYPES)

    @staticmethod
    def _eligible_job():
        return SourceJob(
            source="rss_atom",
            title="Backend Engineer",
            company="Example Labs",
            source_url="https://jobs.example.com/roles/backend",
            source_external_id="backend-1",
            location="Bengaluru, India",
            work_mode="hybrid",
        )


class ConnectorNormalizationTests(unittest.TestCase):
    class FakeResponse:
        def __init__(self, content=b"", data=None, status_code=200, headers=None):
            self.content = content or (
                json.dumps(data).encode("utf-8") if data is not None else b""
            )
            self._data = data
            self.status_code = status_code
            self.headers = headers or {}

        def json(self):
            return self._data

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def iter_bytes(self, chunk_size=65536):
            yield self.content

    class FakeClient:
        def __init__(self, response):
            self.response = response
            self.calls = []

        def stream(self, method, url, **kwargs):
            self.calls.append((url, kwargs))
            return self.response

    @staticmethod
    def _source(connector_type, config):
        return JobSource(
            source_key="connector-test",
            connector_type=connector_type,
            display_name="Connector test",
            config_json=json.dumps(config),
        )

    def test_greenhouse_maps_company_board_fields(self):
        client = self.FakeClient(
            self.FakeResponse(
                data={
                    "jobs": [
                        {
                            "id": 17,
                            "title": "Engineer",
                            "absolute_url": "https://jobs.example.com/17",
                            "location": {"name": "Bengaluru, India"},
                            "content": "<p>Build APIs</p>",
                            "updated_at": "2026-01-01T00:00:00Z",
                        }
                    ]
                }
            )
        )
        connector = GreenhouseConnector(
            self._source(
                "greenhouse",
                {"board_token": "example", "company_name": "Example Labs"},
            ),
            client,
        )

        jobs = connector.discover(JobDiscoveryCriteria(limit=5))

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].company, "Example Labs")
        self.assertEqual(jobs[0].location, "Bengaluru, India")
        self.assertEqual(jobs[0].description, "Build APIs")
        self.assertEqual(jobs[0].source_external_id, "17")
        self.assertIsNone(jobs[0].posted_at)
        self.assertEqual(
            jobs[0].source_updated_at,
            datetime(2026, 1, 1),
        )

    def test_rss_atom_maps_entries_and_rejects_entity_declarations(self):
        payload = b"""<rss><channel><item>
          <title>Engineer</title><company>Example Labs</company>
          <link>https://jobs.example.com/1</link>
          <location>Remote - India</location><description>&lt;p&gt;Build APIs&lt;/p&gt;</description>
        </item></channel></rss>"""
        connector = RSSAtomConnector(
            self._source(
                "rss_atom",
                {"feed_url": "https://jobs.example.com/feed.xml"},
            ),
            self.FakeClient(self.FakeResponse(content=payload)),
        )
        with patch("app.services.connectors.base._validate_public_http_url"):
            jobs = connector.discover(JobDiscoveryCriteria(limit=5))
        self.assertEqual(jobs[0].title, "Engineer")
        self.assertEqual(jobs[0].company, "Example Labs")
        self.assertEqual(jobs[0].description, "Build APIs")

        malicious = RSSAtomConnector(
            self._source(
                "rss_atom",
                {"feed_url": "https://jobs.example.com/feed.xml"},
            ),
            self.FakeClient(
                self.FakeResponse(
                    content=b'<!DOCTYPE x [<!ENTITY e "expanded">]><rss/>'
                )
            ),
        )
        with patch("app.services.connectors.base._validate_public_http_url"):
            with self.assertRaisesRegex(ConnectorError, "entity declarations"):
                malicious.discover(JobDiscoveryCriteria(limit=5))

    def test_mapped_xml_feed_uses_configured_field_paths(self):
        payload = b"""<jobs><job><title>Engineer</title><employer>Example Labs</employer>
          <apply>https://jobs.example.com/1</apply><place>Hyderabad, India</place></job></jobs>"""
        connector = XMLFeedConnector(
            self._source(
                "xml_feed",
                {
                    "feed_url": "https://jobs.example.com/feed.xml",
                    "item_tag": "job",
                    "field_map": {
                        "title": "title",
                        "company": "employer",
                        "url": "apply",
                        "location": "place",
                    },
                },
            ),
            self.FakeClient(self.FakeResponse(content=payload)),
        )
        with patch("app.services.connectors.base._validate_public_http_url"):
            jobs = connector.discover(JobDiscoveryCriteria(limit=5))
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].company, "Example Labs")
        self.assertEqual(jobs[0].location, "Hyderabad, India")

    def test_jobicy_uses_india_filter_and_normalizes_lpa(self):
        client = self.FakeClient(
            self.FakeResponse(
                data={
                    "jobs": [
                        {
                            "id": 9,
                            "jobTitle": "Engineer",
                            "companyName": "Example Labs",
                            "url": "https://jobs.example.com/9",
                            "jobGeo": "India",
                            "annualSalary": "INR 15-25 LPA",
                            "salaryCurrency": "INR",
                        }
                    ]
                }
            )
        )
        connector = JobicyConnector(
            self._source("jobicy", {}),
            client,
        )
        with patch("app.services.connectors.base._validate_public_http_url"):
            jobs = connector.discover(
                JobDiscoveryCriteria(query="Platform Engineer", limit=10)
            )

        self.assertEqual(jobs[0].salary_min, 1_500_000)
        self.assertEqual(jobs[0].salary_max, 2_500_000)
        self.assertEqual(jobs[0].salary_currency, "INR")
        self.assertEqual(jobs[0].salary_period, "annual")
        self.assertEqual(client.calls[0][1]["params"]["geo"], "india")
        self.assertEqual(client.calls[0][1]["params"]["tag"], "Platform Engineer")

    def test_salary_normalization_and_india_eligibility(self):
        compensation = parse_compensation("INR 15-25 LPA")
        self.assertEqual((compensation.minimum, compensation.maximum), (1_500_000, 2_500_000))
        self.assertEqual(compensation.currency, "INR")
        self.assertEqual(compensation.period, "annual")
        global_compensation = parse_compensation("USD 100k-120k per year")
        self.assertEqual(
            (global_compensation.minimum, global_compensation.maximum),
            (100_000, 120_000),
        )
        self.assertEqual(global_compensation.period, "annual")
        self.assertTrue(
            is_india_eligible(
                SourceJob(
                    source="remoteok",
                    title="Engineer",
                    company="Example Labs",
                    location="Remote - APAC",
                )
            )
        )
        self.assertFalse(
            is_india_eligible(
                SourceJob(
                    source="remoteok",
                    title="Engineer",
                    company="Example Labs",
                    location="Remote",
                    work_mode="remote",
                )
            )
        )
        self.assertFalse(
            is_india_eligible(
                SourceJob(
                    source="remoteok",
                    title="Engineer",
                    company="Example Labs",
                    location="Indiana, USA",
                )
            )
        )


class DiscoveryCommandTests(unittest.TestCase):
    def test_cli_uses_only_profile_search_preferences(self):
        candidate = SimpleNamespace(
            id=7,
            full_name="Candidate Name",
            email="candidate@example.com",
            preferred_roles="Backend Engineer",
            preferred_locations="Bengaluru, India",
        )
        run_result = DiscoveryRunResult(
            candidate_id=7,
            source_results=(),
            started_at="2026-01-01T00:00:00+00:00",
            completed_at="2026-01-01T00:00:01+00:00",
        )
        output = StringIO()
        with (
            patch("app.discovery_cli.init_db"),
            patch(
                "app.discovery_cli.candidate_service.get_candidate_by_id",
                return_value=candidate,
            ),
            patch(
                "app.discovery_cli.job_discovery_service.run",
                return_value=run_result,
            ) as run,
            redirect_stdout(output),
        ):
            from app.discovery_cli import main

            exit_code = main(["--candidate-id", "7"])

        criteria = run.call_args.args[1]
        self.assertEqual(exit_code, 0)
        self.assertEqual(criteria.query, "Backend Engineer")
        self.assertEqual(criteria.locations, ("Bengaluru", "India"))
        self.assertTrue(criteria.india_first)
        criteria_text = f"{criteria.query} {' '.join(criteria.locations)}"
        self.assertNotIn(candidate.full_name, criteria_text)
        self.assertNotIn(candidate.email, criteria_text)
        self.assertIn('"candidate_id": 7', output.getvalue())


if __name__ == "__main__":
    unittest.main()
