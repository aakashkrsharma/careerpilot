"""Progressively rank and snapshot application candidates for a batch."""
import json
import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.database.models import Application, ApplicationBatch, Candidate, Job
from app.models.workflow import BatchSelection
from app.services.application_service import ApplicationService, application_service
from app.services.matching_service import MatchingService, matching_service


RELAXATION_STAGES = (
    "strict_match",
    "adjacent_role",
    "location_work_mode",
    "experience",
    "fallback_score",
)

GENERIC_ROLE_WORDS = {
    "associate",
    "developer",
    "engineer",
    "entry",
    "junior",
    "lead",
    "manager",
    "mid",
    "principal",
    "senior",
    "specialist",
    "staff",
}


class BatchSelectionService:
    def __init__(
        self,
        *,
        application_service_instance: Optional[ApplicationService] = None,
        matching_service_instance: Optional[MatchingService] = None,
        reapply_cooldown_days: int = 15,
        company_cooldown_days: int = 0,
    ):
        if application_service_instance is not None:
            self.application_service = application_service_instance
        elif reapply_cooldown_days == 15 and company_cooldown_days == 0:
            self.application_service = application_service
        else:
            self.application_service = ApplicationService(
                reapply_cooldown_days=reapply_cooldown_days,
                company_cooldown_days=company_cooldown_days,
            )
        self.matching_service = matching_service_instance or matching_service

    @staticmethod
    def _tokens(value: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9+#.]+", value.casefold())
            if token not in GENERIC_ROLE_WORDS and len(token) > 1
        }

    def _role_relation(self, candidate: Candidate, job: Job) -> tuple[bool, bool]:
        preferred_roles = self.matching_service.split_values(candidate.preferred_roles)
        if not preferred_roles:
            return True, True
        if self.matching_service.role_match(candidate, job)[0] > 0:
            return True, True
        title_tokens = self._tokens(job.title)
        adjacent = any(
            self._tokens(role).intersection(title_tokens)
            for role in preferred_roles
        )
        return False, adjacent

    def _location_and_mode_match(self, candidate: Candidate, job: Job) -> bool:
        location_score = self.matching_service.location_match(candidate, job)[0]
        mode_score = self.matching_service.work_mode_match(candidate, job)[0]
        return location_score > 0 and mode_score > 0

    @staticmethod
    def _experience_matches(candidate: Candidate, job: Job) -> bool:
        if candidate.years_of_experience is None or job.minimum_experience is None:
            return True
        return candidate.years_of_experience >= job.minimum_experience

    def _stage_for(
        self,
        candidate: Candidate,
        job: Job,
        score: int,
        *,
        matching_threshold: int,
        fallback_score: int,
    ) -> Optional[str]:
        direct_role, adjacent_role = self._role_relation(candidate, job)
        location_mode_match = self._location_and_mode_match(candidate, job)
        experience_match = self._experience_matches(candidate, job)
        role_match = direct_role or adjacent_role

        if (
            score >= matching_threshold
            and direct_role
            and location_mode_match
            and experience_match
        ):
            return "strict_match"
        if (
            score >= matching_threshold
            and adjacent_role
            and location_mode_match
            and experience_match
        ):
            return "adjacent_role"
        if (
            score >= matching_threshold
            and role_match
            and experience_match
        ):
            return "location_work_mode"
        if score >= matching_threshold and role_match:
            return "experience"
        if score >= fallback_score:
            return "fallback_score"
        return None

    def select_batch(
        self,
        candidate_id: int,
        *,
        requested_count: int = 20,
        matching_threshold: int = 70,
        fallback_score: int = 20,
    ) -> BatchSelection:
        if type(requested_count) is not int or requested_count < 1:
            raise ValueError("Requested batch size must be a positive integer.")
        if type(matching_threshold) is not int or not 0 <= matching_threshold <= 100:
            raise ValueError("Matching threshold must be between 0 and 100.")
        if type(fallback_score) is not int or not 0 <= fallback_score <= 100:
            raise ValueError("Fallback score must be between 0 and 100.")
        maximum_count = min(requested_count, 20)
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        with SessionLocal.begin() as db:
            candidate = db.query(Candidate).filter(
                Candidate.id == candidate_id
            ).first()
            if candidate is None:
                raise ValueError("Candidate was not found.")

            scored_jobs = []
            jobs = db.query(Job).order_by(Job.id).all()
            for job in jobs:
                if self.application_service._find_blocking_duplicate_in_session(
                    db,
                    candidate_id,
                    job,
                    now=now,
                ) is not None:
                    continue
                match = self.matching_service.calculate(candidate, job)
                stage = self._stage_for(
                    candidate,
                    job,
                    match.total_score,
                    matching_threshold=matching_threshold,
                    fallback_score=fallback_score,
                )
                if stage is None:
                    continue
                scored_jobs.append((job, match, stage))

            stage_order = {
                name: rank for rank, name in enumerate(RELAXATION_STAGES)
            }
            scored_jobs.sort(
                key=lambda item: (
                    stage_order[item[2]],
                    -item[1].total_score,
                    -len(item[1].matched_skills),
                    item[0].id,
                )
            )
            selected = scored_jobs[:maximum_count]

            batch = ApplicationBatch(
                candidate_id=candidate_id,
                requested_count=maximum_count,
                selected_count=len(selected),
                matching_threshold=matching_threshold,
                relaxation_stages=json.dumps(RELAXATION_STAGES),
                status="draft",
            )
            db.add(batch)
            db.flush()

            for rank, (job, match, stage) in enumerate(selected, start=1):
                self.application_service.create_application_in_session(
                    db,
                    candidate_id=candidate_id,
                    job=job,
                    application_batch_id=batch.id,
                    match_score=match.total_score,
                    match_stage=stage,
                    selected_rank=rank,
                    now=now,
                )

            selection = BatchSelection(
                batch_id=batch.id,
                selected_count=batch.selected_count,
                relaxation_stages=RELAXATION_STAGES,
            )
            return selection

    def get_batches(self, candidate_id: int) -> list[ApplicationBatch]:
        with SessionLocal() as db:
            batches = db.query(ApplicationBatch).filter(
                ApplicationBatch.candidate_id == candidate_id
            ).order_by(
                ApplicationBatch.created_at.desc(),
                ApplicationBatch.id.desc(),
            ).all()
            for batch in batches:
                db.expunge(batch)
            return batches

    def get_batch_applications(
        self,
        batch_id: int,
        candidate_id: int,
    ) -> list[tuple[Application, Job]]:
        with SessionLocal() as db:
            rows = db.query(Application, Job).join(
                Job,
                Job.id == Application.job_id,
            ).filter(
                Application.application_batch_id == batch_id,
                Application.candidate_id == candidate_id,
            ).order_by(Application.selected_rank).all()
            for application, job in rows:
                db.expunge(application)
                db.expunge(job)
            return rows

    def approve_batch(self, batch_id: int, candidate_id: int) -> ApplicationBatch:
        with SessionLocal.begin() as db:
            batch = db.query(ApplicationBatch).filter(
                ApplicationBatch.id == batch_id,
                ApplicationBatch.candidate_id == candidate_id,
            ).first()
            if batch is None:
                raise ValueError("Application batch was not found.")
            if batch.status != "draft":
                raise ValueError("Only a draft batch can be approved.")
            if batch.selected_count == 0:
                raise ValueError("An empty application batch cannot be approved.")
            batch.status = "approved"
            batch.approved_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.flush()
            db.expunge(batch)
            return batch

    def cancel_batch(self, batch_id: int, candidate_id: int) -> ApplicationBatch:
        with SessionLocal.begin() as db:
            batch = db.query(ApplicationBatch).filter(
                ApplicationBatch.id == batch_id,
                ApplicationBatch.candidate_id == candidate_id,
            ).first()
            if batch is None:
                raise ValueError("Application batch was not found.")
            if batch.status != "draft":
                raise ValueError("Only a draft batch can be cancelled.")

            applications = db.query(Application).filter(
                Application.application_batch_id == batch_id,
                Application.candidate_id == candidate_id,
            ).all()
            for application in applications:
                if application.status != "cancelled":
                    self.application_service._transition_in_session(
                        db,
                        application,
                        "cancelled",
                        actor="candidate",
                        reason="Candidate cancelled the draft application batch.",
                        require_tailored_approval=False,
                        tailored_resume_id=None,
                        execution_mode=None,
                        manual_instructions=None,
                        candidate_confirmed=False,
                    )

            batch.status = "cancelled"
            db.flush()
            db.expunge(batch)
            return batch


batch_selection_service = BatchSelectionService()
