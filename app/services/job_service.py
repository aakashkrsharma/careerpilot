"""Local job discovery input, storage, filtering, and deduplication."""
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

import httpx

from app.database.database import SessionLocal
from app.database.models import Job, JobSource, JobSourceListing
from app.models.workflow import JobListingReference, JobUpsertResult, SourceJob


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

    def upsert_normalized_job(
        self,
        source_job: SourceJob,
        *,
        source_id: int,
        source_updated_at: Optional[datetime] = None,
    ) -> JobUpsertResult:
        """Idempotently associate one provider listing with a canonical job."""
        if not isinstance(source_job.title, str) or not source_job.title.strip():
            raise ValueError("Job title is required.")
        if not isinstance(source_job.company, str) or not source_job.company.strip():
            raise ValueError("Company name is required.")
        if not isinstance(source_job.source, str) or not source_job.source.strip():
            raise ValueError("Source is required.")
        if type(source_id) is not int or source_id <= 0:
            raise ValueError("A valid source registry ID is required.")
        for field_name, value in (
            ("Minimum experience", source_job.minimum_experience),
            ("Minimum salary", source_job.salary_min),
            ("Maximum salary", source_job.salary_max),
        ):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{field_name} must be a non-negative integer.")
        if (
            source_job.salary_min is not None
            and source_job.salary_max is not None
            and source_job.salary_min > source_job.salary_max
        ):
            raise ValueError("Minimum salary cannot exceed maximum salary.")
        if source_job.salary_currency and (
            not isinstance(source_job.salary_currency, str)
            or len(source_job.salary_currency.strip()) != 3
        ):
            raise ValueError("Salary currency must be a three-letter code.")

        source_updated_at = source_updated_at or source_job.source_updated_at
        normalized_url = self.normalize_source_url(source_job.source_url)
        source_key = self.create_source_key(
            normalized_url,
            source_job.title,
            source_job.company,
            source_job.location,
        )
        external_id = (
            str(source_job.source_external_id).strip()
            if source_job.source_external_id is not None
            and str(source_job.source_external_id).strip()
            else None
        )
        if external_id:
            listing_key = f"id:{external_id}"
        elif normalized_url:
            listing_key = f"url:{normalized_url}"
        else:
            listing_key = f"hash:{source_key}"

        with SessionLocal.begin() as db:
            listing_query = db.query(JobSourceListing).filter(
                JobSourceListing.source_id == source_id
            )
            listing = (
                listing_query.filter(JobSourceListing.listing_key == listing_key)
                .first()
            )
            if listing is None and normalized_url:
                listing = (
                    listing_query.filter(
                        JobSourceListing.source_url == normalized_url
                    )
                    .first()
                )

            job = (
                db.query(Job).filter(Job.id == listing.job_id).first()
                if listing is not None
                else None
            )
            if job is None:
                job = db.query(Job).filter(Job.source_job_key == source_key).first()
            if job is None and normalized_url:
                job = db.query(Job).filter(Job.source_url == normalized_url).first()
            if job is None:
                job = (
                    db.query(Job)
                    .filter(
                        func.lower(Job.title) == source_job.title.strip().lower(),
                        func.lower(Job.company) == source_job.company.strip().lower(),
                        func.lower(func.coalesce(Job.location, ""))
                        == (source_job.location or "").strip().lower(),
                    )
                    .first()
                )

            created = job is None
            if created:
                job = Job(
                    source=source_job.source.strip().lower(),
                    source_url=normalized_url,
                    source_job_key=source_key,
                    title=source_job.title.strip(),
                    company=source_job.company.strip(),
                    location=_clean(source_job.location),
                    work_mode=_clean(source_job.work_mode),
                    description=_clean(source_job.description),
                    required_skills=_clean(source_job.required_skills),
                    minimum_experience=source_job.minimum_experience,
                    salary_min=source_job.salary_min,
                    salary_max=source_job.salary_max,
                    salary_currency=_clean(source_job.salary_currency).upper()
                    if _clean(source_job.salary_currency)
                    else None,
                    salary_period=_clean(source_job.salary_period),
                    salary_text=_clean(source_job.salary_text),
                    posted_at=source_job.posted_at,
                )
                db.add(job)
                db.flush()
                updated = False
            else:
                replace_values = listing is not None and listing.job_id == job.id
                updated = _merge_source_job(
                    job,
                    source_job,
                    normalized_url,
                    replace_values=replace_values,
                )

            if listing is None:
                listing = JobSourceListing(
                    source_id=source_id,
                    job_id=job.id,
                    listing_key=listing_key,
                    external_id=external_id,
                    source_url=normalized_url,
                    source_updated_at=source_updated_at,
                )
                db.add(listing)
                db.flush()
            else:
                listing.job_id = job.id
                listing.external_id = external_id or listing.external_id
                listing.source_url = normalized_url or listing.source_url
                listing.source_updated_at = source_updated_at or listing.source_updated_at
                listing.last_seen_at = datetime.now(timezone.utc).replace(
                    tzinfo=None
                )
                db.flush()

            result = JobUpsertResult(
                job_id=job.id,
                listing_id=listing.id,
                created=created,
                updated=updated,
                matched_existing=not created,
            )
            return result

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

    def import_job_from_url(self, url: str) -> Job:
        normalized = self.normalize_source_url(url)
        if normalized is None:
            raise ValueError("A complete http or https URL is required.")
        response = httpx.get(
            normalized,
            timeout=15.0,
            follow_redirects=False,
            headers={"User-Agent": "CareerPilot/1.0 (respectful job import)"},
        )
        response.raise_for_status()
        html = response.text[:2_000_000]
        title = None
        company = None
        description = None
        location = None
        match = re.search(
            r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            try:
                payload = json.loads(match.group(1).strip())
                if isinstance(payload, list):
                    payload = payload[0] if payload else {}
                if payload.get("@type") == "JobPosting":
                    title = payload.get("title")
                    company = (payload.get("hiringOrganization") or {}).get("name")
                    description = payload.get("description")
                    location = (
                        (payload.get("jobLocation") or {}).get("address", {}).get("addressLocality")
                        if isinstance(payload.get("jobLocation"), dict)
                        else None
                    )
            except (json.JSONDecodeError, AttributeError):
                pass
        if not title:
            title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip() if title_match else "Imported job"
        if not company:
            company = "Unknown company"
        if not description:
            description = "Imported from public URL. Review and edit before use."
        return self.create_job(
            title=title,
            company=company,
            source="manual_url_import",
            source_url=normalized,
            location=location,
            work_mode=None,
            description=description,
            required_skills=None,
            minimum_experience=None,
            salary_min=None,
            salary_max=None,
        )

    def get_job_source_listings(self, job_id: int) -> list[JobListingReference]:
        with SessionLocal() as db:
            rows = (
                db.query(JobSourceListing, JobSource.display_name)
                .join(JobSource, JobSource.id == JobSourceListing.source_id)
                .filter(JobSourceListing.job_id == job_id)
                .order_by(JobSource.display_name, JobSourceListing.id)
                .all()
            )
            return [
                JobListingReference(
                    source_name=display_name,
                    source_url=listing.source_url,
                    external_id=listing.external_id,
                )
                for listing, display_name in rows
            ]

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


def _clean(value: Optional[str]) -> Optional[str]:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _merge_source_job(
    job: Job,
    source_job: SourceJob,
    normalized_url: Optional[str],
    *,
    replace_values: bool,
) -> bool:
    changes = {
        "title": source_job.title.strip(),
        "company": source_job.company.strip(),
        "source_url": normalized_url,
        "location": _clean(source_job.location),
        "work_mode": _clean(source_job.work_mode),
        "description": _clean(source_job.description),
        "required_skills": _clean(source_job.required_skills),
        "minimum_experience": source_job.minimum_experience,
        "salary_min": source_job.salary_min,
        "salary_max": source_job.salary_max,
        "salary_currency": _clean(source_job.salary_currency).upper()
        if _clean(source_job.salary_currency)
        else None,
        "salary_period": _clean(source_job.salary_period),
        "salary_text": _clean(source_job.salary_text),
        "posted_at": source_job.posted_at,
    }
    changed = False
    for field_name, incoming in changes.items():
        if incoming is None:
            continue
        current = getattr(job, field_name)
        if replace_values or current in (None, ""):
            if current != incoming:
                setattr(job, field_name, incoming)
                changed = True
    return changed
