"""Screening-question reuse and candidate clarification workflow."""
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional

from app.database.database import SessionLocal
from app.database.models import (
    Application,
    ClarificationRequest,
    Job,
)
from app.models.workflow import ClarificationAssessment
from app.services.answer_bank_service import (
    AnswerBankService,
    VALID_SENSITIVITY,
    answer_bank_service,
)
from app.services.application_service import ApplicationService, application_service


HIGH_STAKES_TERMS = (
    "salary",
    "compensation",
    "ctc",
    "work authorization",
    "right to work",
    "visa",
    "sponsorship",
    "relocation",
    "criminal",
    "disability",
)


@dataclass(frozen=True)
class ClarificationQueueItem:
    request: ClarificationRequest
    application: Application
    job: Job


class ClarificationQueueService:
    def __init__(
        self,
        *,
        answer_service: Optional[AnswerBankService] = None,
        application_service_instance: Optional[ApplicationService] = None,
    ):
        self.answer_service = answer_service or answer_bank_service
        self.application_service = (
            application_service_instance or application_service
        )

    def _sensitivity(self, question: dict) -> str:
        supplied = question.get("sensitivity", "normal")
        if supplied not in VALID_SENSITIVITY:
            raise ValueError("Question sensitivity is invalid.")
        text = " ".join(
            str(question.get(key) or "")
            for key in ("question_text", "canonical_key", "category")
        ).casefold()
        normalized_text = re.sub(r"[^a-z0-9]+", " ", text).strip()
        if supplied != "high_stakes" and any(
            re.search(rf"\b{re.escape(term)}\b", normalized_text)
            for term in HIGH_STAKES_TERMS
        ):
            return "high_stakes"
        return supplied

    def assess_questions(
        self,
        application_id: int,
        candidate_id: int,
        questions: Iterable[dict],
    ) -> ClarificationAssessment:
        auto_answers: dict[str, str] = {}
        request_ids: list[int] = []
        requests_to_create: list[dict] = []

        with SessionLocal.begin() as db:
            application, job = db.query(Application, Job).join(
                Job,
                Job.id == Application.job_id,
            ).filter(
                Application.id == application_id,
                Application.candidate_id == candidate_id,
            ).first() or (None, None)
            if application is None or job is None:
                raise ValueError("Application was not found for this candidate.")

            for question in questions:
                if not isinstance(question, dict):
                    raise ValueError("Each screening question must be a mapping.")
                text = question.get("question_text")
                if not isinstance(text, str) or not text.strip():
                    raise ValueError("Question text is required.")
                canonical_key = self.answer_service.normalize_key(
                    question.get("canonical_key") or text
                )
                ambiguous = question.get("ambiguous", False)
                required = question.get("required", True)
                if type(ambiguous) is not bool or type(required) is not bool:
                    raise ValueError("Question ambiguity and required flags must be boolean.")
                sensitivity = self._sensitivity(question)
                category = question.get("category")
                if category is not None and not isinstance(category, str):
                    raise ValueError("Question category must be text.")

                answer = self.answer_service.resolve_answer(
                    candidate_id=candidate_id,
                    canonical_key=canonical_key,
                    scope_hints={
                        "job": str(job.id),
                        "company": job.company,
                        "role": job.title,
                        "source": job.source,
                    },
                )
                needs_clarification = (
                    required
                    and (
                        answer is None
                        or ambiguous
                        or sensitivity == "high_stakes"
                    )
                )
                if not needs_clarification:
                    if answer is not None:
                        auto_answers[canonical_key] = answer.answer_text
                    continue

                existing = db.query(ClarificationRequest).filter(
                    ClarificationRequest.application_id == application_id,
                    ClarificationRequest.canonical_key == canonical_key,
                    ClarificationRequest.is_resolved.is_(False),
                ).first()
                if existing is not None:
                    request_ids.append(existing.id)
                    continue
                requests_to_create.append({
                    "canonical_key": canonical_key,
                    "question_text": text.strip(),
                    "proposed_answer": answer.answer_text if answer else (
                        str(question.get("proposed_answer") or "").strip() or None
                    ),
                    "category": category.strip() if category and category.strip() else None,
                    "sensitivity": sensitivity,
                })

            for request_data in requests_to_create:
                request = ClarificationRequest(
                    application_id=application_id,
                    save_to_answer_bank=False,
                    is_resolved=False,
                    **request_data,
                )
                db.add(request)
                db.flush()
                request_ids.append(request.id)

            if request_ids and application.status != "needs_clarification":
                self.application_service._transition_in_session(
                    db,
                    application,
                    "needs_clarification",
                    actor="system",
                    reason="Screening questions require candidate clarification.",
                    require_tailored_approval=False,
                    tailored_resume_id=None,
                    execution_mode=None,
                    manual_instructions=None,
                    candidate_confirmed=False,
                )

        return ClarificationAssessment(
            auto_answers=auto_answers,
            request_ids=tuple(request_ids),
        )

    def get_queue(
        self,
        candidate_id: int,
        *,
        unresolved_only: bool = True,
    ) -> list[ClarificationQueueItem]:
        with SessionLocal() as db:
            query = db.query(
                ClarificationRequest,
                Application,
                Job,
            ).join(
                Application,
                Application.id == ClarificationRequest.application_id,
            ).join(
                Job,
                Job.id == Application.job_id,
            ).filter(Application.candidate_id == candidate_id)
            if unresolved_only:
                query = query.filter(ClarificationRequest.is_resolved.is_(False))
            rows = query.order_by(
                ClarificationRequest.created_at,
                ClarificationRequest.id,
            ).all()
            items = []
            for request, application, job in rows:
                db.expunge(request)
                db.expunge(application)
                db.expunge(job)
                items.append(ClarificationQueueItem(request, application, job))
            return items

    def resolve_request(
        self,
        request_id: int,
        candidate_id: int,
        *,
        candidate_answer: str,
        candidate_approved: bool,
        save_to_answer_bank: bool,
        scope: str = "global",
        scope_value: Optional[str] = None,
        aliases: Optional[str] = None,
    ) -> ClarificationRequest:
        if candidate_approved is not True:
            raise ValueError("Candidate approval is required to save this answer.")
        if type(save_to_answer_bank) is not bool:
            raise ValueError("Answer-bank choice must be boolean.")
        if not isinstance(candidate_answer, str) or not candidate_answer.strip():
            raise ValueError("Candidate answer is required.")

        with SessionLocal.begin() as db:
            request = db.query(ClarificationRequest).join(
                Application,
                Application.id == ClarificationRequest.application_id,
            ).filter(
                ClarificationRequest.id == request_id,
                Application.candidate_id == candidate_id,
            ).first()
            if request is None:
                raise ValueError("Clarification request was not found.")
            if request.is_resolved:
                raise ValueError("Clarification request is already resolved.")

            application = db.query(Application).filter(
                Application.id == request.application_id,
                Application.candidate_id == candidate_id,
            ).first()
            if application is None:
                raise ValueError("Application was not found for this candidate.")

            request.candidate_answer = candidate_answer.strip()
            request.save_to_answer_bank = save_to_answer_bank
            if save_to_answer_bank:
                self.answer_service.upsert_answer(
                    candidate_id=candidate_id,
                    canonical_key=request.canonical_key,
                    answer_text=candidate_answer,
                    scope=scope,
                    scope_value=scope_value,
                    sensitivity=request.sensitivity,
                    aliases=aliases,
                    is_approved=True,
                    source_application_id=request.application_id,
                    db_session=db,
                )
            request.is_resolved = True
            request.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.flush()
            db.expunge(request)

        remaining = self.get_queue(candidate_id)
        if not any(
            item.application.id == request.application_id
            for item in remaining
        ):
            application = next(
                (
                    item.application
                    for item in self.get_queue(candidate_id, unresolved_only=False)
                    if item.application.id == request.application_id
                ),
                None,
            )
            if application is not None and application.status == "needs_clarification":
                self.application_service.transition_status(
                    application.id,
                    candidate_id,
                    "ready",
                    actor="candidate",
                    reason="Candidate resolved all screening clarifications.",
                )
        return request


clarification_queue_service = ClarificationQueueService()
