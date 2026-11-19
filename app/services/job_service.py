"""Local job discovery input, storage, filtering, and deduplication."""
import hashlib
from datetime import datetime
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.exc import IntegrityError

from app.database.database import SessionLocal
from app.database.models import Job


TRACKING_PARAMETERS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
}


class JobService:
    def normalize_source_url(self, source_url: Optional[str]) -> Optional[str]:
        if not isinstance(source_url, str) or not source_url.strip():
            return None
        url = source_url.strip()
        split = urlsplit(url)
        if not split.scheme or not split.netloc:
            raise ValueError("Source URL must be a complete http or https URL.")
        if split.scheme.lower() not in ("http", "https"):
            raise ValueError("Source URL must use http or https.")
        query = [
            (key, value)
            for key, value in parse_qsl(split.query, keep_blank_values=True)
            if key.lower() not in TRACKING_PARAMETERS
        ]
        normalized = urlunsplit(
            (
                split.scheme.lower(),
                split.netloc.lower(),
                split.path.rstrip("/") or "/",
                urlencode(sorted(query)),
                "",
            )
        )
        return normalized

    def create_source_key(
        self,
        source_url: Optional[str],
        title: str,
        company: str,
        location: Optional[str],
    ) -> str:
        if source_url:
            return self.normalize_source_url(source_url) or ""
        identity = "||".join(
            (
                title.strip().lower(),
                company.strip().lower(),
                (location or "").strip().lower(),
            )
        )
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    def create_job(
        self,
        *,
        title: str,
        company: str,
        source: str = "manual",
        source_url: Optional[str] = None,
        location: Optional[str] = None,
        work_mode: Optional[str] = None,
        description: Optional[str] = None,
        required_skills: Optional[str] = None,
        minimum_experience: Optional[int] = None,
        salary_min: Optional[int] = None,
        salary_max: Optional[int] = None,
        posted_at: Optional[datetime] = None,
    ) -> Job:
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Job title is required.")
        if not isinstance(company, str) or not company.strip():
            raise ValueError("Company name is required.")
        if not isinstance(source, str) or not source.strip():
            raise ValueError("Source is required.")

        normalized_url = self.normalize_source_url(source_url)
        source_key = self.create_source_key(
            normalized_url,
            title,
            company,
            location,
        )
        for field_name, value in (
            ("Minimum experience", minimum_experience),
            ("Minimum salary", salary_min),
            ("Maximum salary", salary_max),
        ):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{field_name} must be a non-negative integer.")
        if (
            salary_min is not None
            and salary_max is not None
            and salary_min > salary_max
        ):
            raise ValueError("Minimum salary cannot exceed maximum salary.")

        try:
            with SessionLocal.begin() as db:
                job = Job(
                    source=source.strip().lower(),
                    source_url=normalized_url,
                    source_job_key=source_key,
                    title=title.strip(),
                    company=company.strip(),
                    location=location.strip() if location and location.strip() else None,
                    work_mode=work_mode.strip() if work_mode and work_mode.strip() else None,
                    description=description.strip() if description and description.strip() else None,
                    required_skills=required_skills.strip()
                    if required_skills and required_skills.strip()
                    else None,
                    minimum_experience=minimum_experience,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    posted_at=posted_at,
                )
                db.add(job)
                db.flush()
                db.expunge(job)
                return job
        except IntegrityError as exc:
            raise ValueError(
                "This job already exists for the selected source."
            ) from exc

    def get_jobs(self) -> list[Job]:
        with SessionLocal() as db:
            jobs = db.query(Job).order_by(Job.created_at.desc(), Job.id.desc()).all()
            for job in jobs:
                db.expunge(job)
            return jobs

    def get_job_by_id(self, job_id: int) -> Optional[Job]:
        with SessionLocal() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job is not None:
                db.expunge(job)
            return job

    def filter_jobs(
        self,
        *,
        title_or_company: Optional[str] = None,
        location: Optional[str] = None,
        work_mode: Optional[str] = None,
        required_skills: Optional[str] = None,
        maximum_experience: Optional[int] = None,
    ) -> list[Job]:
        jobs = self.get_jobs()
        term = title_or_company.strip().lower() if title_or_company else ""
        location_term = location.strip().lower() if location else ""
        work_mode_term = work_mode.strip().lower() if work_mode else ""
        skill_terms = [
            skill.strip().lower()
            for skill in (required_skills or "").split(",")
            if skill.strip()
        ]

        filtered = []
        for job in jobs:
            searchable = f"{job.title} {job.company}".lower()
            if term and term not in searchable:
                continue
            if location_term:
                location_terms = [
                    item.strip().lower()
                    for item in location_term.split(",")
                    if item.strip()
                ]
                job_location = (job.location or "").lower()
                if not any(
                    item in job_location for item in location_terms
                ):
                    continue
            if work_mode_term:
                if (job.work_mode or "").lower() != work_mode_term:
                    continue
            if maximum_experience is not None:
                if (
                    job.minimum_experience is not None
                    and job.minimum_experience > maximum_experience
                ):
                    continue
            if skill_terms:
                job_skills = (job.required_skills or "").lower()
                if not all(skill in job_skills for skill in skill_terms):
                    continue
            filtered.append(job)
        return filtered


job_service = JobService()
