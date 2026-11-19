"""Persistence and approval workflow for resume extraction results."""
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError

from app.database.database import SessionLocal
from app.database.models import Candidate, ExtractedInfo, Resume


EXTRACTED_FIELDS = (
    "full_name",
    "email",
    "phone",
    "location",
    "linkedin",
    "github",
    "summary",
    "experience",
    "skills",
    "education",
)

PROFILE_FIELDS = (
    "full_name",
    "email",
    "phone",
    "location",
    "linkedin",
    "github",
    "summary",
    "experience",
    "skills",
    "education",
)


class ExtractionService:
    def save_pending_extraction(self, result: dict[str, Any]) -> int:
        """Persist validated model output as unreviewed information."""
        if not isinstance(result, dict):
            raise ValueError("Extraction result must be an object.")
        if result.get("error"):
            raise ValueError("Cannot save a failed resume extraction.")

        candidate_id = result.get("candidate_id")
        resume_id = result.get("resume_id")
        if type(candidate_id) is not int or type(resume_id) is not int:
            raise ValueError("Extraction result must include candidate and resume IDs.")

        data = result.get("extracted_data")
        if not isinstance(data, dict):
            raise ValueError("Extraction result must contain an extracted-data object.")

        fields: dict[str, Optional[str]] = {}
        for field in EXTRACTED_FIELDS:
            value = data.get(field)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"Extracted field '{field}' must be text or null.")
            fields[field] = value
        if not any(value and value.strip() for value in fields.values()):
            raise ValueError("Extraction returned no candidate information to review.")

        prompt = result.get("prompt_used")
        response = result.get("llm_response")
        if not isinstance(prompt, str) or not isinstance(response, str):
            raise ValueError("Extraction result must include its prompt and raw response.")

        with SessionLocal.begin() as db:
            resume = db.query(Resume).filter(
                Resume.id == resume_id,
                Resume.candidate_id == candidate_id,
            ).first()
            if resume is None:
                raise ValueError("Resume was not found for the selected candidate.")

            extraction = ExtractedInfo(
                candidate_id=candidate_id,
                resume_id=resume_id,
                **fields,
                is_reviewed=False,
                is_approved=False,
                prompt_used=prompt,
                llm_response=response,
            )
            db.add(extraction)
            resume.is_processed = True
            db.flush()
            return extraction.id

    def get_extraction_for_resume(
        self,
        candidate_id: int,
        resume_id: int,
    ) -> Optional[dict[str, Any]]:
        """Return the latest extraction for the specified candidate/resume pair."""
        with SessionLocal() as db:
            extraction = (
                db.query(ExtractedInfo)
                .filter(
                    ExtractedInfo.candidate_id == candidate_id,
                    ExtractedInfo.resume_id == resume_id,
                )
                .order_by(ExtractedInfo.id.desc())
                .first()
            )
            if extraction is None:
                return None

            return {
                "id": extraction.id,
                **{field: getattr(extraction, field) for field in EXTRACTED_FIELDS},
                "is_reviewed": extraction.is_reviewed,
                "is_approved": extraction.is_approved,
                "reviewed_at": extraction.reviewed_at,
                "approved_at": extraction.approved_at,
                "prompt_used": extraction.prompt_used,
                "llm_response": extraction.llm_response,
            }

    def save_review(
        self,
        extraction_id: int,
        candidate_id: int,
        updated_fields: dict[str, Any],
        is_approved: bool,
        replace_existing: bool = False,
    ) -> None:
        """Save reviewed fields and apply approved values in one transaction."""
        if not isinstance(is_approved, bool) or not isinstance(replace_existing, bool):
            raise ValueError("Review and replacement choices must be boolean.")
        if not isinstance(updated_fields, dict):
            raise ValueError("Reviewed information must be an object.")

        fields: dict[str, Optional[str]] = {}
        for field in EXTRACTED_FIELDS:
            value = updated_fields.get(field)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"Reviewed field '{field}' must be text or empty.")
            fields[field] = value

        try:
            with SessionLocal.begin() as db:
                extraction = (
                    db.query(ExtractedInfo)
                    .filter(
                        ExtractedInfo.id == extraction_id,
                        ExtractedInfo.candidate_id == candidate_id,
                    )
                    .first()
                )
                if extraction is None:
                    raise ValueError("Extraction was not found for this candidate.")

                candidate = db.query(Candidate).filter(
                    Candidate.id == candidate_id,
                ).first()
                if candidate is None:
                    raise ValueError("Candidate for this extraction was not found.")

                for field, value in fields.items():
                    setattr(extraction, field, value)

                now = datetime.now(timezone.utc).replace(tzinfo=None)
                extraction.is_reviewed = True
                extraction.is_approved = is_approved
                extraction.reviewed_at = now
                extraction.approved_at = now if is_approved else None

                if is_approved:
                    for field in PROFILE_FIELDS:
                        approved_value = (fields[field] or "").strip()
                        current_value = getattr(candidate, field)
                        has_existing_value = bool(
                            current_value and current_value.strip()
                        )
                        if approved_value and (
                            replace_existing or not has_existing_value
                        ):
                            setattr(candidate, field, approved_value)
        except IntegrityError as exc:
            raise ValueError(
                "The profile update conflicts with existing data; candidate email "
                "addresses must be unique."
            ) from exc


extraction_service = ExtractionService()
