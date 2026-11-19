"""Typed value objects shared by discovery and application workflows."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class JobDiscoveryCriteria:
    query: Optional[str] = None
    locations: tuple[str, ...] = (
        "Bengaluru",
        "Hyderabad",
        "Pune",
        "Delhi NCR",
        "Mumbai",
        "Chennai",
        "India - Remote",
    )
    roles: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    work_modes: tuple[str, ...] = ()
    limit: int = 100
    india_first: bool = True


@dataclass(frozen=True)
class SourceJob:
    source: str
    title: str
    company: str
    source_url: Optional[str] = None
    source_external_id: Optional[str] = None
    location: Optional[str] = None
    work_mode: Optional[str] = None
    description: Optional[str] = None
    posted_at: Optional[datetime] = None
    source_updated_at: Optional[datetime] = None
    required_skills: Optional[str] = None
    minimum_experience: Optional[int] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None
    salary_period: Optional[str] = None
    salary_text: Optional[str] = None


@dataclass(frozen=True)
class JobUpsertResult:
    job_id: int
    listing_id: int
    created: bool
    updated: bool
    matched_existing: bool


@dataclass(frozen=True)
class JobListingReference:
    source_name: str
    source_url: Optional[str]
    external_id: Optional[str]


@dataclass(frozen=True)
class SourceRunResult:
    source_key: str
    display_name: str
    status: str
    fetched_count: int = 0
    created_count: int = 0
    updated_count: int = 0
    duplicate_count: int = 0
    cooldown_count: int = 0
    excluded_region_count: int = 0
    error_message: Optional[str] = None


@dataclass(frozen=True)
class DiscoveryRunResult:
    candidate_id: int
    source_results: tuple[SourceRunResult, ...]
    started_at: str
    completed_at: str


@dataclass(frozen=True)
class BatchSelection:
    batch_id: int
    selected_count: int
    relaxation_stages: tuple[str, ...]


@dataclass(frozen=True)
class ClarificationAssessment:
    auto_answers: dict[str, str]
    request_ids: tuple[int, ...]


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    execution_mode: str
    message: str
    manual_instructions: Optional[str] = None
