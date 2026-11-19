"""Typed value objects shared by discovery and application workflows."""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class JobDiscoveryCriteria:
    query: Optional[str] = None
    locations: tuple[str, ...] = ()
    roles: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    work_modes: tuple[str, ...] = ()
    limit: int = 100


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
    required_skills: Optional[str] = None
    minimum_experience: Optional[int] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None


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
