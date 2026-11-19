"""Local Ollama resume-tailoring drafts with explicit review and approval."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
import ollama
from pydantic import ValidationError

from app.database.database import SessionLocal
from app.database.models import Candidate, Job, Resume, TailoredResume
from app.models.tailored_resume import TailoredResumeOutput


class TailoringService:
    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model_name = os.getenv("OLLAMA_MODEL", "llama3")
        self.client = ollama.Client(host=self.base_url)
        self.output_dir = Path("data") / "tailored_resumes"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_prompt(
        self,
        candidate: Candidate,
        job: Job,
        source_resume_text: Optional[str],
    ) -> str:
        facts = {
            "full_name": candidate.full_name,
            "email": candidate.email,
            "phone": candidate.phone,
            "location": candidate.location,
            "linkedin": candidate.linkedin,
            "github": candidate.github,
            "summary": candidate.summary,
            "experience": candidate.experience,
            "skills": candidate.skills,
            "education": candidate.education,
            "years_of_experience": candidate.years_of_experience,
        }
        job_facts = {
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "work_mode": job.work_mode,
            "description": job.description,
            "required_skills": job.required_skills,
            "minimum_experience": job.minimum_experience,
        }
        return f"""
You are a resume-writing assistant. Create a job-specific resume draft using ONLY
the verified facts below. Do not add employers, jobs, degrees, dates, metrics,
skills, certifications, locations, names, or achievements that are not present.
Prefer omitted details over uncertain or invented details.

Return only a JSON object with exactly these fields:
- draft_text: complete plain-text resume draft
- suggestions: array of review suggestions
- limitations: array of any missing facts or weak areas

Verified candidate facts:
{json.dumps(facts, ensure_ascii=False)}

Optional source resume text:
{source_resume_text or "No source resume text provided."}

Target job facts:
{json.dumps(job_facts, ensure_ascii=False)}
"""

    def generate_draft(
        self,
        candidate_id: int,
        job_id: int,
        resume_id: Optional[int] = None,
    ) -> dict:
        with SessionLocal() as db:
            candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
            job = db.query(Job).filter(Job.id == job_id).first()
            resume = None
            if resume_id is not None:
                resume = db.query(Resume).filter(
                    Resume.id == resume_id,
                    Resume.candidate_id == candidate_id,
                ).first()

        if candidate is None:
            raise ValueError("Candidate was not found.")
        if job is None:
            raise ValueError("Job was not found.")
        if resume_id is not None and resume is None:
            raise ValueError("Resume was not found for this candidate.")

        prompt = self.create_prompt(
            candidate,
            job,
            resume.extracted_text if resume is not None else None,
        )
        raw_response = self._get_llm_response(prompt)
        output = self._parse_response(raw_response)
        return {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "resume_id": resume_id,
            "prompt": prompt,
            "raw_response": raw_response,
            "draft_text": output.draft_text,
            "suggestions": output.suggestions,
            "limitations": output.limitations,
        }

    def _get_llm_response(self, prompt: str) -> str:
        try:
            response = self.client.generate(
                model=self.model_name,
                prompt=prompt,
                stream=False,
            )
        except (ollama.ResponseError, httpx.HTTPError) as exc:
            raise ValueError(f"Local Ollama tailoring failed: {exc}") from exc
        return response.response

    def _parse_response(self, raw_response: str) -> TailoredResumeOutput:
        if not isinstance(raw_response, str):
            raise ValueError("Tailoring response must be text.")
        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise ValueError("Tailoring response must be valid JSON.") from exc
        try:
            output = TailoredResumeOutput.model_validate(parsed)
        except ValidationError as exc:
            raise ValueError("Tailoring response has an invalid structure.") from exc
        if not output.draft_text.strip():
            raise ValueError("Tailoring response returned an empty draft.")
        if any(marker in output.draft_text.lower() for marker in (
            "[insert",
            "[add",
            "placeholder",
        )):
            raise ValueError(
                "Tailoring response contains placeholders; human review is required."
            )
        return output

    def save_draft(
        self,
        candidate_id: int,
        job_id: int,
        resume_id: Optional[int],
        draft_text: str,
        suggestions: list[str],
        limitations: list[str],
        prompt: str,
        raw_response: str,
    ) -> int:
        if not isinstance(draft_text, str) or not draft_text.strip():
            raise ValueError("Draft text is required.")
        with SessionLocal.begin() as db:
            candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
            job = db.query(Job).filter(Job.id == job_id).first()
            if candidate is None or job is None:
                raise ValueError("Candidate and job must both exist.")
            draft = TailoredResume(
                candidate_id=candidate_id,
                job_id=job_id,
                resume_id=resume_id,
                draft_text=draft_text.strip(),
                suggestions="\n".join(suggestions),
                limitations="\n".join(limitations),
                prompt_used=prompt,
                llm_response=raw_response,
                is_reviewed=False,
                is_approved=False,
            )
            db.add(draft)
            db.flush()
            return draft.id

    def get_drafts(
        self,
        candidate_id: int,
        job_id: Optional[int] = None,
    ) -> list[TailoredResume]:
        with SessionLocal() as db:
            query = db.query(TailoredResume).filter(
                TailoredResume.candidate_id == candidate_id
            )
            if job_id is not None:
                query = query.filter(TailoredResume.job_id == job_id)
            drafts = query.order_by(
                TailoredResume.created_at.desc(),
                TailoredResume.id.desc(),
            ).all()
            for draft in drafts:
                db.expunge(draft)
            return drafts

    def review_draft(
        self,
        draft_id: int,
        candidate_id: int,
        draft_text: str,
        suggestions: str,
        limitations: str,
        is_approved: bool,
    ) -> TailoredResume:
        if not isinstance(is_approved, bool):
            raise ValueError("Approval choice must be boolean.")
        if not isinstance(draft_text, str) or not draft_text.strip():
            raise ValueError("Reviewed draft text is required.")

        with SessionLocal.begin() as db:
            draft = db.query(TailoredResume).filter(
                TailoredResume.id == draft_id,
                TailoredResume.candidate_id == candidate_id,
            ).first()
            if draft is None:
                raise ValueError("Tailored resume was not found for this candidate.")
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            draft.draft_text = draft_text.strip()
            draft.suggestions = suggestions.strip() or None
            draft.limitations = limitations.strip() or None
            draft.is_reviewed = True
            draft.is_approved = is_approved
            draft.reviewed_at = now
            draft.approved_at = now if is_approved else None
            db.flush()
            db.expunge(draft)
            return draft

    def export_draft(self, draft_id: int, candidate_id: int) -> str:
        with SessionLocal() as db:
            draft = db.query(TailoredResume).filter(
                TailoredResume.id == draft_id,
                TailoredResume.candidate_id == candidate_id,
            ).first()
            if draft is None:
                raise ValueError("Tailored resume was not found.")
            if not draft.is_approved:
                raise ValueError("The tailored resume must be approved before export.")
            draft_text = draft.draft_text
            job = db.query(Job).filter(Job.id == draft.job_id).first()

        candidate_dir = self.output_dir / str(candidate_id)
        candidate_dir.mkdir(parents=True, exist_ok=True)
        safe_title = "".join(
            character if character.isalnum() or character in ("-", "_") else "_"
            for character in (job.title if job is not None else "resume")
        ).strip("_") or "resume"
        path = candidate_dir / f"{safe_title}-job-{draft.job_id}-draft-{draft.id}.txt"
        path.write_text(draft_text, encoding="utf-8")

        with SessionLocal.begin() as db:
            draft = db.query(TailoredResume).filter(
                TailoredResume.id == draft_id
            ).first()
            draft.exported_path = str(path)
        return str(path)


tailoring_service = TailoringService()
