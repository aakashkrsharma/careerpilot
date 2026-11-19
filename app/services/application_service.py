"""Application history, cooldown checks, and status transitions."""
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.database.models import (
    Application,
    ApplicationBatch,
    ApplicationStatusEvent,
    Candidate,
    ClarificationRequest,
    Job,
    TailoredResume,
)


ACTIVE_APPLICATION_STATUSES = {
    "discovered",
    "tailored",
    "needs_clarification",
    "ready",
    "submitted",
    "manual_required",
}

VALID_APPLICATION_STATUSES = {
    *ACTIVE_APPLICATION_STATUSES,
    "applied",
    "follow_up",
    "cancelled",
    "rejected",
    "withdrawn",
    "interview",
    "offer",
}

ALLOWED_TRANSITIONS = {
    "discovered": {"tailored", "needs_clarification", "ready", "cancelled"},
    "tailored": {"needs_clarification", "ready", "cancelled"},
    "needs_clarification": {"tailored", "ready", "cancelled"},
    "ready": {
        "submitted",
        "manual_required",
        "needs_clarification",
        "cancelled",
    },
    "manual_required": {"applied", "cancelled"},
    "submitted": {
        "applied",
        "rejected",
        "withdrawn",
        "interview",
        "offer",
        "manual_required",
    },
    "applied": {"follow_up", "withdrawn", "interview", "offer", "rejected"},
    "interview": {"offer", "rejected", "withdrawn"},
    "offer": {"withdrawn", "rejected"},
}


class ApplicationService:
    def __init__(
        self,
        *,
        reapply_cooldown_days: int = 15,
        company_cooldown_days: int = 0,
    ):
        self.reapply_cooldown_days = self._validate_cooldown(
            "Reapply cooldown", reapply_cooldown_days
        )
        self.company_cooldown_days = self._validate_cooldown(
            "Company cooldown", company_cooldown_days
        )

    @staticmethod
    def _validate_cooldown(label: str, days: int) -> int:
        if type(days) is not int or days < 0:
            raise ValueError(f"{label} must be a non-negative integer.")
        return days

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _as_naive_utc(value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def normalize_source_url(self, source_url: Optional[str]) -> Optional[str]:
        if not source_url:
            return None
        if not isinstance(source_url, str) or not source_url.strip():
            return None
        split = urlsplit(source_url.strip())
        if split.scheme.lower() not in {"http", "https"} or not split.netloc:
            raise ValueError("Source URL must be a complete http or https URL.")
        tracking = {
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "ref",
        }
        query = [
            (key, value)
            for key, value in parse_qsl(split.query, keep_blank_values=True)
            if key.lower() not in tracking
        ]
        return urlunsplit((
            split.scheme.lower(),
            split.netloc.lower(),
            split.path.rstrip("/") or "/",
            urlencode(sorted(query)),
            "",
        ))

    def build_dedup_key(
        self,
        job: Job,
        source_external_id: Optional[str] = None,
    ) -> str:
        normalized_url = self.normalize_source_url(job.source_url)
        if normalized_url:
            return normalized_url
        if source_external_id:
            identity = (
                f"external::{job.source.lower()}::"
                f"{source_external_id.strip().lower()}"
            )
            return hashlib.sha256(identity.encode("utf-8")).hexdigest()
        identity = "||".join((
            job.title.strip().lower(),
            job.company.strip().lower(),
            (job.location or "").strip().lower(),
        ))
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    def _same_job(
        self,
        application: Application,
        existing_job: Job,
        job: Job,
        dedup_key: str,
    ) -> bool:
        if application.dedup_key == dedup_key:
            return True
        existing_url = self.normalize_source_url(existing_job.source_url)
        incoming_url = self.normalize_source_url(job.source_url)
        same_url = bool(existing_url and incoming_url and existing_url == incoming_url)
        same_manual_identity = (
            existing_job.title.strip().lower() == job.title.strip().lower()
            and existing_job.company.strip().lower() == job.company.strip().lower()
            and (existing_job.location or "").strip().lower()
            == (job.location or "").strip().lower()
        )
        return same_url or same_manual_identity

    def _within_cooldown(
        self,
        application: Application,
        *,
        now: datetime,
        cooldown_days: int,
    ) -> bool:
        if cooldown_days == 0:
            return False
        timestamp = application.applied_at or application.submitted_at
        if timestamp is None:
            return False
        last_application = self._as_naive_utc(timestamp)
        return now <= last_application + timedelta(days=cooldown_days)

    def _find_blocking_duplicate_in_session(
        self,
        db: Session,
        candidate_id: int,
        job: Job,
        *,
        dedup_key: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> Optional[Application]:
        incoming_key = dedup_key or self.build_dedup_key(job)
        current_time = self._as_naive_utc(now or self._utc_now())
        candidates = db.query(Application, Job).join(
            Job,
            Job.id == Application.job_id,
        ).filter(
            Application.candidate_id == candidate_id,
        ).all()

        for application, existing_job in candidates:
            if application.status in ACTIVE_APPLICATION_STATUSES and self._same_job(
                application, existing_job, job, incoming_key
            ):
                return application

        for application, existing_job in candidates:
            if not self._same_job(application, existing_job, job, incoming_key):
                continue
            if self._within_cooldown(
                application,
                now=current_time,
                cooldown_days=self.reapply_cooldown_days,
            ):
                return application

        if self.company_cooldown_days:
            company = job.company.strip().casefold()
            for application, existing_job in candidates:
                different_role = (
                    existing_job.title.strip().casefold()
                    != job.title.strip().casefold()
                )
                if (
                    existing_job.company.strip().casefold() == company
                    and different_role
                    and self._within_cooldown(
                        application,
                        now=current_time,
                        cooldown_days=self.company_cooldown_days,
                    )
                ):
                    return application
        return None

    def find_blocking_duplicate(
        self,
        candidate_id: int,
        job: Job,
        source_external_id: Optional[str] = None,
        *,
        now: Optional[datetime] = None,
    ) -> Optional[Application]:
        dedup_key = self.build_dedup_key(job, source_external_id)
        with SessionLocal() as db:
            application = self._find_blocking_duplicate_in_session(
                db,
                candidate_id,
                job,
                dedup_key=dedup_key,
                now=now,
            )
            if application is not None:
                db.expunge(application)
            return application

    def create_application_in_session(
        self,
        db: Session,
        *,
        candidate_id: int,
        job: Job,
        application_batch_id: Optional[int] = None,
        tailored_resume_id: Optional[int] = None,
        source_external_id: Optional[str] = None,
        match_score: Optional[int] = None,
        match_stage: Optional[str] = None,
        selected_rank: Optional[int] = None,
        execution_mode: str = "not_started",
        now: Optional[datetime] = None,
    ) -> Application:
        if db.query(Candidate.id).filter(Candidate.id == candidate_id).first() is None:
            raise ValueError("Candidate was not found.")
        if application_batch_id is not None:
            batch = db.query(ApplicationBatch).filter(
                ApplicationBatch.id == application_batch_id,
                ApplicationBatch.candidate_id == candidate_id,
            ).first()
            if batch is None:
                raise ValueError("Application batch was not found for this candidate.")
        if tailored_resume_id is not None:
            tailored = db.query(TailoredResume).filter(
                TailoredResume.id == tailored_resume_id,
                TailoredResume.candidate_id == candidate_id,
            ).first()
            if tailored is None:
                raise ValueError("Tailored resume was not found for this candidate.")

        dedup_key = self.build_dedup_key(job, source_external_id)
        duplicate = self._find_blocking_duplicate_in_session(
            db,
            candidate_id,
            job,
            dedup_key=dedup_key,
            now=now,
        )
        if duplicate is not None:
            if duplicate.status in ACTIVE_APPLICATION_STATUSES:
                raise ValueError(
                    "An active application already exists for this candidate and job."
                )
            previous_job = db.query(Job).filter(
                Job.id == duplicate.job_id
            ).first()
            if previous_job is not None and self._same_job(
                duplicate,
                previous_job,
                job,
                dedup_key,
            ):
                raise ValueError(
                    f"This job is within the {self.reapply_cooldown_days}-day "
                    "reapply cooldown."
                )
            raise ValueError(
                f"This company is within the {self.company_cooldown_days}-day "
                "reapply cooldown."
            )

        created_at = self._as_naive_utc(now or self._utc_now())
        application = Application(
            candidate_id=candidate_id,
            job_id=job.id,
            tailored_resume_id=tailored_resume_id,
            application_batch_id=application_batch_id,
            dedup_key=dedup_key,
            source=job.source,
            source_url=self.normalize_source_url(job.source_url),
            source_external_id=source_external_id.strip()
            if source_external_id and source_external_id.strip()
            else None,
            status="discovered",
            execution_mode=execution_mode,
            match_score=match_score,
            match_stage=match_stage,
            selected_rank=selected_rank,
            discovered_at=created_at,
        )
        db.add(application)
        db.flush()
        db.add(ApplicationStatusEvent(
            application_id=application.id,
            from_status=None,
            to_status="discovered",
            actor="system",
            reason="Application record created.",
        ))
        db.flush()
        return application

    def create_application(
        self,
        *,
        candidate_id: int,
        job_id: int,
        application_batch_id: Optional[int] = None,
        tailored_resume_id: Optional[int] = None,
        source_external_id: Optional[str] = None,
        match_score: Optional[int] = None,
        match_stage: Optional[str] = None,
        selected_rank: Optional[int] = None,
        execution_mode: str = "not_started",
    ) -> Application:
        try:
            with SessionLocal.begin() as db:
                job = db.query(Job).filter(Job.id == job_id).first()
                if job is None:
                    raise ValueError("Job was not found.")
                application = self.create_application_in_session(
                    db,
                    candidate_id=candidate_id,
                    job=job,
                    application_batch_id=application_batch_id,
                    tailored_resume_id=tailored_resume_id,
                    source_external_id=source_external_id,
                    match_score=match_score,
                    match_stage=match_stage,
                    selected_rank=selected_rank,
                    execution_mode=execution_mode,
                )
                db.flush()
                db.expunge(application)
                return application
        except IntegrityError as exc:
            raise ValueError(
                "An active application already exists for this candidate and job."
            ) from exc

    def _transition_in_session(
        self,
        db: Session,
        application: Application,
        to_status: str,
        *,
        actor: str,
        reason: str,
        require_tailored_approval: bool,
        tailored_resume_id: Optional[int],
        execution_mode: Optional[str],
        manual_instructions: Optional[str],
        candidate_confirmed: bool,
    ) -> Application:
        allowed = ALLOWED_TRANSITIONS.get(application.status, set())
        if to_status not in allowed:
            raise ValueError(
                f"Cannot transition application from {application.status} to {to_status}."
            )
        if to_status == "applied" and candidate_confirmed is not True:
            raise ValueError(
                "Explicit candidate confirmation is required to mark applied."
            )

        if application.application_batch_id is not None and to_status not in {
            "cancelled",
            "rejected",
            "withdrawn",
        }:
            batch = db.query(ApplicationBatch).filter(
                ApplicationBatch.id == application.application_batch_id,
                ApplicationBatch.candidate_id == application.candidate_id,
            ).first()
            if batch is None or batch.status != "approved":
                raise ValueError("Approve this application batch before continuing.")

        if tailored_resume_id is not None:
            tailored = db.query(TailoredResume).filter(
                TailoredResume.id == tailored_resume_id,
                TailoredResume.candidate_id == application.candidate_id,
                TailoredResume.job_id == application.job_id,
                TailoredResume.is_approved.is_(True),
            ).first()
            if tailored is None:
                raise ValueError(
                    "An approved tailored resume for this job is required."
                )
            application.tailored_resume_id = tailored_resume_id

        resume_id = application.tailored_resume_id
        if (require_tailored_approval or to_status == "ready") and resume_id is not None:
            tailored = db.query(TailoredResume).filter(
                TailoredResume.id == resume_id,
                TailoredResume.candidate_id == application.candidate_id,
                TailoredResume.job_id == application.job_id,
                TailoredResume.is_approved.is_(True),
            ).first()
            if tailored is None:
                raise ValueError(
                    "A tailored resume must be approved before this transition."
                )

        if to_status == "ready":
            unresolved = db.query(ClarificationRequest.id).filter(
                ClarificationRequest.application_id == application.id,
                ClarificationRequest.is_resolved.is_(False),
            ).first()
            if unresolved is not None:
                raise ValueError(
                    "Resolve all clarification requests before marking the "
                    "application ready."
                )

        now = self._utc_now()
        from_status = application.status
        application.status = to_status
        if execution_mode is not None:
            application.execution_mode = execution_mode
        if manual_instructions is not None:
            application.manual_instructions = manual_instructions
        if to_status == "tailored":
            application.tailored_at = now
        elif to_status == "needs_clarification":
            application.clarification_at = now
        elif to_status == "ready":
            application.ready_at = now
        elif to_status == "submitted":
            application.submitted_at = now
        elif to_status == "applied":
            application.applied_at = now
        elif to_status == "follow_up":
            application.follow_up_at = now

        db.add(ApplicationStatusEvent(
            application_id=application.id,
            from_status=from_status,
            to_status=to_status,
            actor=actor,
            reason=reason,
        ))
        db.flush()
        return application

    def transition_status(
        self,
        application_id: int,
        candidate_id: int,
        to_status: str,
        *,
        actor: str = "candidate",
        reason: str,
        require_tailored_approval: bool = False,
        tailored_resume_id: Optional[int] = None,
        execution_mode: Optional[str] = None,
        manual_instructions: Optional[str] = None,
        candidate_confirmed: bool = False,
    ) -> Application:
        if actor not in {"system", "candidate", "connector"}:
            raise ValueError("Status event actor is invalid.")
        if to_status not in VALID_APPLICATION_STATUSES:
            raise ValueError("Application status is invalid.")
        with SessionLocal.begin() as db:
            application = db.query(Application).filter(
                Application.id == application_id,
                Application.candidate_id == candidate_id,
            ).first()
            if application is None:
                raise ValueError("Application was not found for this candidate.")
            application = self._transition_in_session(
                db,
                application,
                to_status,
                actor=actor,
                reason=reason,
                require_tailored_approval=require_tailored_approval,
                tailored_resume_id=tailored_resume_id,
                execution_mode=execution_mode,
                manual_instructions=manual_instructions,
                candidate_confirmed=candidate_confirmed,
            )
            db.expunge(application)
            return application

    def prepare_manual_handoff(
        self,
        application_id: int,
        candidate_id: int,
        *,
        candidate_approved: bool,
        instructions: str,
    ) -> Application:
        if candidate_approved is not True:
            raise ValueError("Candidate approval is required for a manual handoff.")
        if not isinstance(instructions, str) or not instructions.strip():
            raise ValueError("Manual handoff instructions are required.")
        return self.transition_status(
            application_id,
            candidate_id,
            "manual_required",
            actor="candidate",
            reason="Candidate requested a manual application handoff.",
            execution_mode="manual",
            manual_instructions=instructions.strip(),
        )

    def confirm_manual_application(
        self,
        application_id: int,
        candidate_id: int,
        *,
        candidate_confirmed: bool,
    ) -> Application:
        if candidate_confirmed is not True:
            raise ValueError("Candidate confirmation is required to mark applied.")
        with SessionLocal() as db:
            application = db.query(Application).filter(
                Application.id == application_id,
                Application.candidate_id == candidate_id,
            ).first()
            if application is None:
                raise ValueError("Application was not found for this candidate.")
            if application.status != "manual_required":
                raise ValueError(
                    "Only a manual handoff can be confirmed through this action."
                )
        return self.confirm_application(
            application_id,
            candidate_id,
            candidate_confirmed=candidate_confirmed,
        )

    def confirm_application(
        self,
        application_id: int,
        candidate_id: int,
        *,
        candidate_confirmed: bool,
    ) -> Application:
        if candidate_confirmed is not True:
            raise ValueError("Candidate confirmation is required to mark applied.")
        return self.transition_status(
            application_id,
            candidate_id,
            "applied",
            actor="candidate",
            reason="Candidate confirmed the application was submitted.",
            candidate_confirmed=True,
        )

    def get_application_history(self, candidate_id: int) -> list[Application]:
        with SessionLocal() as db:
            applications = db.query(Application).filter(
                Application.candidate_id == candidate_id
            ).order_by(Application.created_at.desc(), Application.id.desc()).all()
            for application in applications:
                db.expunge(application)
            return applications

    def get_status_counts(self, candidate_id: int) -> dict[str, int]:
        counts: dict[str, int] = {}
        for application in self.get_application_history(candidate_id):
            counts[application.status] = counts.get(application.status, 0) + 1
        return counts


application_service = ApplicationService()
