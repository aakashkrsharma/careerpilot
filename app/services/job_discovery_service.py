"""Rate-limited orchestration for compliant job-source connectors."""
from datetime import datetime, timedelta, timezone
import logging
import time
from typing import Callable, Optional

import httpx

from app.database.database import SessionLocal
from app.database.models import Candidate, JobSource
from app.models.workflow import (
    DiscoveryRunResult,
    JobDiscoveryCriteria,
    SourceJob,
    SourceRunResult,
)
from app.services.application_service import ApplicationService
from app.services.connectors import create_connector
from app.services.connectors.base import ConnectorError
from app.services.discovery_policy import is_india_eligible
from app.services.job_service import JobService, job_service
from app.services.job_source_registry_service import (
    JobSourceRegistryService,
    job_source_registry_service,
)


logger = logging.getLogger(__name__)
MAX_BACKOFF_SECONDS = 24 * 60 * 60


class JobDiscoveryService:
    def __init__(
        self,
        *,
        registry: JobSourceRegistryService = job_source_registry_service,
        jobs: JobService = job_service,
        applications: Optional[ApplicationService] = None,
        connector_factory: Callable = create_connector,
        clock: Optional[Callable[[], datetime]] = None,
        request_interval_seconds: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if request_interval_seconds < 0:
            raise ValueError("Request interval cannot be negative.")
        self.registry = registry
        self.jobs = jobs
        self.applications = applications or ApplicationService()
        self.connector_factory = connector_factory
        self.clock = clock or _utc_now
        self.request_interval_seconds = request_interval_seconds
        self.sleep = sleep

    def run(
        self,
        candidate_id: int,
        criteria: JobDiscoveryCriteria,
        *,
        source_ids: Optional[set[int]] = None,
        progress_callback: Optional[Callable[[SourceRunResult], None]] = None,
    ) -> DiscoveryRunResult:
        if type(candidate_id) is not int or candidate_id <= 0:
            raise ValueError("A valid candidate is required for discovery.")
        if not isinstance(criteria, JobDiscoveryCriteria):
            raise ValueError("Valid job discovery criteria are required.")
        if type(criteria.limit) is not int or not 1 <= criteria.limit <= 500:
            raise ValueError("Discovery limit must be between 1 and 500.")
        with SessionLocal() as db:
            if db.query(Candidate.id).filter(Candidate.id == candidate_id).first() is None:
                raise ValueError("Candidate was not found.")

        started = self.clock()
        results: list[SourceRunResult] = []
        sources = self.registry.get_sources(
            enabled_only=True,
            source_ids=source_ids,
        )
        last_request_monotonic = None
        for source in sources:
            now = self.clock()
            if _rate_limited(source, now):
                result = SourceRunResult(
                    source_key=source.source_key,
                    display_name=source.display_name,
                    status="rate_limited",
                )
                results.append(result)
                if progress_callback:
                    progress_callback(result)
                continue

            if last_request_monotonic is not None:
                elapsed = time.monotonic() - last_request_monotonic
                if elapsed < self.request_interval_seconds:
                    self.sleep(self.request_interval_seconds - elapsed)
            self._mark_running(source.id, now)
            last_request_monotonic = time.monotonic()
            try:
                with httpx.Client(follow_redirects=False) as client:
                    connector = self.connector_factory(source, client)
                    source_jobs = list(connector.discover(criteria))
                result = self._process_source(
                    source,
                    source_jobs,
                    candidate_id=candidate_id,
                    criteria=criteria,
                    now=now,
                )
                self._mark_finished(source.id, result, now=self.clock())
            except Exception as exc:
                logger.error(
                    "Job discovery failed for source %s (%s): %s",
                    source.source_key,
                    source.connector_type,
                    type(exc).__name__,
                )
                result = self._failure_result(source, exc)
                self._mark_failed(source.id, exc, now=self.clock())
            results.append(result)
            if progress_callback:
                progress_callback(result)

        completed = self.clock()
        return DiscoveryRunResult(
            candidate_id=candidate_id,
            source_results=tuple(results),
            started_at=started.isoformat(),
            completed_at=completed.isoformat(),
        )

    def _process_source(
        self,
        source: JobSource,
        source_jobs: list[SourceJob],
        *,
        candidate_id: int,
        criteria: JobDiscoveryCriteria,
        now: datetime,
    ) -> SourceRunResult:
        fetched = len(source_jobs[: criteria.limit])
        created = updated = duplicate = cooldown = excluded = 0
        for source_job in source_jobs[: criteria.limit]:
            if not isinstance(source_job, SourceJob):
                raise ValueError("Connector returned a non-normalized job record.")
            if criteria.india_first and not is_india_eligible(source_job):
                excluded += 1
                continue
            upsert = self.jobs.upsert_normalized_job(
                source_job,
                source_id=source.id,
                source_updated_at=source_job.source_updated_at,
            )
            if upsert.created:
                created += 1
            elif upsert.updated:
                updated += 1
            else:
                duplicate += 1
            job = self.jobs.get_job_by_id(upsert.job_id)
            if job is None:
                raise RuntimeError("Upserted job could not be reloaded.")
            if self.applications.find_blocking_duplicate(
                candidate_id,
                job,
                source_external_id=source_job.source_external_id,
                now=now,
            ):
                cooldown += 1

        return SourceRunResult(
            source_key=source.source_key,
            display_name=source.display_name,
            status="success",
            fetched_count=fetched,
            created_count=created,
            updated_count=updated,
            duplicate_count=duplicate,
            cooldown_count=cooldown,
            excluded_region_count=excluded,
        )

    def _mark_running(self, source_id: int, now: datetime) -> None:
        with SessionLocal.begin() as db:
            source = db.query(JobSource).filter(JobSource.id == source_id).first()
            if source is None:
                raise ValueError("Source was not found.")
            source.last_run_at = _naive_utc(now)
            source.next_allowed_at = _naive_utc(
                now + timedelta(seconds=source.min_interval_seconds)
            )
            source.last_status = "running"
            source.last_error = None

    def _mark_finished(
        self,
        source_id: int,
        result: SourceRunResult,
        *,
        now: datetime,
    ) -> None:
        with SessionLocal.begin() as db:
            source = db.query(JobSource).filter(JobSource.id == source_id).first()
            if source is None:
                raise ValueError("Source was not found.")
            source.last_run_at = _naive_utc(now)
            source.last_success_at = _naive_utc(now)
            source.next_allowed_at = _naive_utc(
                now + timedelta(seconds=source.min_interval_seconds)
            )
            source.last_status = "success"
            source.last_error = None
            source.consecutive_failures = 0
            source.last_fetched_count = result.fetched_count
            source.last_created_count = result.created_count
            source.last_updated_count = result.updated_count
            source.last_duplicate_count = result.duplicate_count
            source.last_cooldown_count = result.cooldown_count
            source.last_excluded_region_count = result.excluded_region_count

    def _mark_failed(self, source_id: int, error: Exception, *, now: datetime) -> None:
        with SessionLocal.begin() as db:
            source = db.query(JobSource).filter(JobSource.id == source_id).first()
            if source is None:
                return
            source.consecutive_failures += 1
            multiplier = 2 ** min(source.consecutive_failures - 1, 5)
            delay = min(
                source.min_interval_seconds * multiplier,
                MAX_BACKOFF_SECONDS,
            )
            if isinstance(error, ConnectorError) and error.retry_after_seconds:
                delay = min(
                    max(error.retry_after_seconds, source.min_interval_seconds),
                    MAX_BACKOFF_SECONDS,
                )
            source.next_allowed_at = _naive_utc(now + timedelta(seconds=delay))
            source.last_status = "failed"
            source.last_error = _safe_error_message(error)
            source.last_fetched_count = 0
            source.last_created_count = 0
            source.last_updated_count = 0
            source.last_duplicate_count = 0
            source.last_cooldown_count = 0
            source.last_excluded_region_count = 0

    @staticmethod
    def _failure_result(source: JobSource, error: Exception) -> SourceRunResult:
        return SourceRunResult(
            source_key=source.source_key,
            display_name=source.display_name,
            status="failed",
            error_message=_safe_error_message(error),
        )


def _rate_limited(source: JobSource, now: datetime) -> bool:
    next_allowed = source.next_allowed_at
    if next_allowed is not None:
        return _naive_utc(next_allowed) > _naive_utc(now)
    if source.last_run_at is None:
        return False
    return (
        _naive_utc(source.last_run_at)
        + timedelta(seconds=source.min_interval_seconds)
        > _naive_utc(now)
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _safe_error_message(error: Exception) -> str:
    if isinstance(error, ConnectorError):
        return str(error)[:1000]
    return f"Unexpected {type(error).__name__}; see application logs."


job_discovery_service = JobDiscoveryService()
