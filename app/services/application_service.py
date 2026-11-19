"""Permanent application history, deduplication, and status transitions."""
import hashlib
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.exc import IntegrityError

from app.database.database import SessionLocal
from app.database.models import (
    Application,
    ApplicationStatusEvent,
    Job,
    TailoredResume,
)


VALID_APPLICATION_STATUSES = {
    "discovered",
    "tailored",
    "needs_clarification",
    "ready",
    "submitted",
    "applied",
    "follow_up",
    "manual_required",
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
    "ready": {"submitted", "manual_required", "cancelled"},
    "manual_required": {"applied", "cancelled"},
    "submitted": {"applied", "rejected", "withdrawn", "interview", "offer", "manual_required"},
    "applied": {"follow_up", "withdrawn", "interview", "offer", "rejected"},
    "interview": {"offer", "rejected", "withdrawn"},
    "offer": {"withdrawn", "rejected"},
}


class ApplicationService:
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
            identity = f"external::{job.source.lower()}::{source_external_id.strip().lower()}"
            return hashlib.sha256(identity.encode("utf-8")).hexdigest()
        identity = "||".join((
            job.title.strip().lower(),
            job.company.strip().lower(),
            (job.location or "").strip().lower(),
        ))
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    def find_permanent_duplicate(
        self,
        candidate_id: int,
        job: Job,
        source_external_id: Optional[str] = None,
    ) -> Optional[Application]:
        dedup_key = self.build_dedup_key(job, source_external_id)
        with SessionLocal() as db:
            application = db.query(Application).filter(
                Application.candidate_id == candidate_id,
                Application.dedup_key == dedup_key,
            ).first()
            if application is None:
                identity_title = job.title.strip().lower()
                identity_company = job.company.strip().lower()
                identity_location = (job.location or "").strip().lower()
                candidates = db.query(Application, Job).join(
                    Job,
                    Job.id == Application.job_id,
                ).filter(
                    Application.candidate_id == candidate_id,
                ).all()
                for existing_application, existing_job in candidates:
                    same_manual_identity = (
                        existing_job.title.strip().lower() == identity_title
                        and existing_job.company.strip().lower() == identity_company
                        and (existing_job.location or "").strip().lower()
                        == identity_location
                    )
                    existing_url = self.normalize_source_url(existing_job.source_url)
                    incoming_url = self.normalize_source_url(job.source_url)
                    same_url = (
                        bool(existing_url)
                        and bool(incoming_url)
                        and existing_url == incoming_url
                    )
                    if same_manual_identity or same_url:
                        application = existing_application
                        break
            if application is not None:
                db.expunge(application)
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
        with SessionLocal.begin() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job is None:
                raise ValueError("Job was not found.")
            if tailored_resume_id is not None:
                tailored_resume = db.query(TailoredResume).filter(
                    TailoredResume.id == tailored_resume_id,
                    TailoredResume.candidate_id == candidate_id,
                ).first()
                if tailored_resume is None:
                    raise ValueError("Tailored resume was not found for this candidate.")

            dedup_key = self.build_dedup_key(job, source_external_id)
            existing = db.query(Application).filter(
                Application.candidate_id == candidate_id,
                Application.dedup_key == dedup_key,
            ).first()
            if existing is None:
                candidate_applications = db.query(Application, Job).join(
                    Job,
                    Job.id == Application.job_id,
                ).filter(
                    Application.candidate_id == candidate_id,
                ).all()
                incoming_url = self.normalize_source_url(job.source_url)
                for old_application, old_job in candidate_applications:
                    same_manual_identity = (
                        old_job.title.strip().lower() == job.title.strip().lower()
                        and old_job.company.strip().lower()
                        == job.company.strip().lower()
                        and (old_job.location or "").strip().lower()
                        == (job.location or "").strip().lower()
                    )
                    old_url = self.normalize_source_url(old_job.source_url)
                    same_url = bool(incoming_url and old_url and incoming_url == old_url)
                    if same_manual_identity or same_url:
                        existing = old_application
                        break
            if existing is not None:
                db.expunge(existing)
                raise ValueError(
                    "A permanent application record already exists for this candidate and job."
                )

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            application = Application(
                candidate_id=candidate_id,
                job_id=job_id,
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
                discovered_at=now,
            )
            db.add(application)
            db.flush()
            db.add(ApplicationStatusEvent(
                application_id=application.id,
                from_status=None,
                to_status="discovered",
                actor="system",
                reason="Permanent application record created.",
            ))
            db.flush()
            db.expunge(application)
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
            allowed = ALLOWED_TRANSITIONS.get(application.status, set())
            if to_status not in allowed:
                raise ValueError(
                    f"Cannot transition application from {application.status} to {to_status}."
                )

            if require_tailored_approval and application.tailored_resume_id is not None:
                tailored = db.query(TailoredResume).filter(
                    TailoredResume.id == application.tailored_resume_id,
                    TailoredResume.is_approved.is_(True),
                ).first()
                if tailored is None:
                    raise ValueError(
                        "A tailored resume must be approved before this transition."
                    )

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            from_status = application.status
            application.status = to_status
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
            db.expunge(application)
            return application

    def get_application_history(self, candidate_id: int) -> list[Application]:
        with SessionLocal() as db:
            applications = db.query(Application).filter(
                Application.candidate_id == candidate_id
            ).order_by(Application.created_at.desc(), Application.id.desc()).all()
            for application in applications:
                db.expunge(application)
            return applications


application_service = ApplicationService()
