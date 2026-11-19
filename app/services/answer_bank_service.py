"""Scoped, approved reusable answers for application screening questions."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.database.models import CandidateAnswerBank


VALID_SCOPES = {"global", "role", "company", "source", "job"}
VALID_SENSITIVITY = {"normal", "sensitive", "high_stakes"}


class AnswerBankService:
    def normalize_key(self, key: str) -> str:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Answer canonical key is required.")
        return "_".join(key.strip().lower().replace("-", " ").split())

    def normalize_scope_value(self, scope: str, scope_value: str | None) -> str:
        if scope == "global":
            return ""
        if not isinstance(scope_value, str) or not scope_value.strip():
            raise ValueError("Scoped answers require a scope value.")
        return scope_value.strip().lower()

    def upsert_answer(
        self,
        *,
        candidate_id: int,
        canonical_key: str,
        answer_text: str,
        scope: str = "global",
        scope_value: Optional[str] = None,
        sensitivity: str = "normal",
        aliases: Optional[str] = None,
        is_approved: bool = False,
        source_application_id: Optional[int] = None,
        expires_at: Optional[datetime] = None,
        db_session: Optional[Session] = None,
    ) -> CandidateAnswerBank:
        key = self.normalize_key(canonical_key)
        if scope not in VALID_SCOPES:
            raise ValueError("Answer scope is invalid.")
        if sensitivity not in VALID_SENSITIVITY:
            raise ValueError("Answer sensitivity is invalid.")
        if not isinstance(answer_text, str) or not answer_text.strip():
            raise ValueError("Answer text is required.")
        if sensitivity in {"sensitive", "high_stakes"} and not is_approved:
            raise ValueError(
                "Sensitive and high-stakes answers require explicit approval."
            )
        normalized_scope_value = self.normalize_scope_value(scope, scope_value)

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        def persist(db: Session) -> CandidateAnswerBank:
            existing = db.query(CandidateAnswerBank).filter(
                CandidateAnswerBank.candidate_id == candidate_id,
                CandidateAnswerBank.canonical_key == key,
                CandidateAnswerBank.scope == scope,
                CandidateAnswerBank.scope_value == normalized_scope_value,
            ).first()
            if existing is not None:
                existing.answer_text = answer_text.strip()
                existing.aliases = aliases.strip() if aliases and aliases.strip() else None
                existing.sensitivity = sensitivity
                existing.is_approved = is_approved
                existing.approved_at = now if is_approved else None
                existing.source_application_id = source_application_id
                existing.expires_at = expires_at
                db.flush()
                if db_session is None:
                    db.expunge(existing)
                return existing

            entry = CandidateAnswerBank(
                candidate_id=candidate_id,
                canonical_key=key,
                aliases=aliases.strip() if aliases and aliases.strip() else None,
                answer_text=answer_text.strip(),
                scope=scope,
                scope_value=normalized_scope_value,
                sensitivity=sensitivity,
                is_approved=is_approved,
                source_application_id=source_application_id,
                approved_at=now if is_approved else None,
                expires_at=expires_at,
            )
            db.add(entry)
            db.flush()
            if db_session is None:
                db.expunge(entry)
            return entry

        try:
            if db_session is not None:
                return persist(db_session)
            with SessionLocal.begin() as db:
                return persist(db)
        except IntegrityError as exc:
            raise ValueError(
                "The answer bank entry conflicts with an existing scoped answer."
            ) from exc

    def resolve_answer(
        self,
        *,
        candidate_id: int,
        canonical_key: str,
        scope_hints: Optional[dict[str, str]] = None,
    ) -> Optional[CandidateAnswerBank]:
        key = self.normalize_key(canonical_key)
        hints = scope_hints or {}
        precedence = [
            ("job", hints.get("job")),
            ("company", hints.get("company")),
            ("role", hints.get("role")),
            ("source", hints.get("source")),
            ("global", ""),
        ]
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with SessionLocal() as db:
            for scope, scope_value in precedence:
                if scope != "global" and not scope_value:
                    continue
                entry = db.query(CandidateAnswerBank).filter(
                    CandidateAnswerBank.candidate_id == candidate_id,
                    CandidateAnswerBank.canonical_key == key,
                    CandidateAnswerBank.scope == scope,
                    CandidateAnswerBank.scope_value == (
                        scope_value.strip().lower()
                        if isinstance(scope_value, str)
                        else ""
                    ),
                    CandidateAnswerBank.is_approved.is_(True),
                ).first()
                if entry is not None:
                    if entry.expires_at is not None and entry.expires_at <= now:
                        continue
                    db.expunge(entry)
                    return entry
            entries = db.query(CandidateAnswerBank).filter(
                CandidateAnswerBank.candidate_id == candidate_id,
                CandidateAnswerBank.is_approved.is_(True),
            ).all()
            for entry in entries:
                aliases = [
                    self.normalize_key(alias)
                    for alias in (entry.aliases or "").replace("\n", ",").split(",")
                    if alias.strip()
                ]
                if key not in aliases:
                    continue
                if entry.expires_at is not None and entry.expires_at <= now:
                    continue
                scope_rank = {
                    "job": 0,
                    "company": 1,
                    "role": 2,
                    "source": 3,
                    "global": 4,
                }
                matching_hint = {
                    "job": hints.get("job"),
                    "company": hints.get("company"),
                    "role": hints.get("role"),
                    "source": hints.get("source"),
                    "global": "",
                }.get(entry.scope)
                if entry.scope != "global" and (
                    not matching_hint
                    or matching_hint.strip().lower() != entry.scope_value
                ):
                    continue
                db.expunge(entry)
                return entry
        return None

    def get_answers(self, candidate_id: int) -> list[CandidateAnswerBank]:
        with SessionLocal() as db:
            entries = db.query(CandidateAnswerBank).filter(
                CandidateAnswerBank.candidate_id == candidate_id
            ).order_by(
                CandidateAnswerBank.canonical_key,
                CandidateAnswerBank.scope,
            ).all()
            for entry in entries:
                db.expunge(entry)
            return entries


answer_bank_service = AnswerBankService()
