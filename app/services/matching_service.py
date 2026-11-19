"""Deterministic, explainable candidate-to-job compatibility scoring."""
import re
from typing import Iterable

from app.database.models import Candidate, Job
from app.models.job import JobMatchResult


class MatchingService:
    def split_values(self, value: str | None) -> list[str]:
        if not value:
            return []
        values = []
        for item in re.split(r"[,;/|\n]+", value):
            normalized = " ".join(item.strip().lower().split())
            if normalized and normalized not in values:
                values.append(normalized)
        return values

    def get_job_skills(self, job: Job) -> list[str]:
        if job.required_skills:
            return self.split_values(job.required_skills)
        if job.description:
            known = {
                "python",
                "sql",
                "javascript",
                "typescript",
                "java",
                "c++",
                "c#",
                "go",
                "rust",
                "react",
                "node.js",
                "django",
                "flask",
                "fastapi",
                "pandas",
                "pydantic",
                "sqlalchemy",
                "streamlit",
                "aws",
                "azure",
                "gcp",
                "docker",
                "kubernetes",
                "git",
                "linux",
            }
            description = job.description.lower()
            return [skill for skill in known if re.search(
                rf"(?<![a-z0-9]){re.escape(skill)}(?![a-z0-9])",
                description,
            )]
        return []

    def skill_match(
        self,
        candidate: Candidate,
        job: Job,
    ) -> tuple[int, list[str], list[str], str]:
        candidate_skills = set(self.split_values(candidate.skills))
        job_skills = self.get_job_skills(job)
        if not job_skills:
            return 20, [], [], "No specific required skills were provided."

        matched = [skill for skill in job_skills if skill in candidate_skills]
        missing = [skill for skill in job_skills if skill not in candidate_skills]
        score = round(50 * len(matched) / len(job_skills))
        return (
            score,
            matched,
            missing,
            f"Skills matched {len(matched)} of {len(job_skills)} required skills.",
        )

    def experience_match(
        self,
        candidate: Candidate,
        job: Job,
    ) -> tuple[int, str]:
        candidate_years = candidate.years_of_experience
        required_years = job.minimum_experience
        if required_years is None:
            return 20, "Job does not specify a minimum experience level."
        if candidate_years is None:
            return 0, "Candidate experience level is not set."
        if candidate_years >= required_years:
            return 20, (
                f"Experience meets the {required_years}-year requirement "
                f"({candidate_years} years recorded)."
            )
        gap = required_years - candidate_years
        return (
            max(0, round(20 * candidate_years / required_years)),
            f"Experience is {gap} year(s) below the {required_years}-year requirement.",
        )

    def location_match(
        self,
        candidate: Candidate,
        job: Job,
    ) -> tuple[int, str]:
        preferred_locations = set(self.split_values(candidate.preferred_locations))
        job_location = (job.location or "").strip().lower()
        if not preferred_locations:
            return 10, "No preferred locations are set."
        if not job_location:
            return 10, "Job location is not specified."
        if job_location in preferred_locations or any(
            location in job_location or job_location in location
            for location in preferred_locations
        ):
            return 15, f"Location matches preference: {job.location}."
        return 0, f"Location preference differs from {job.location}."

    def work_mode_match(
        self,
        candidate: Candidate,
        job: Job,
    ) -> tuple[int, str]:
        preferred_modes = set(
            mode.strip().lower()
            for mode in (candidate.work_modes or "").split(",")
            if mode.strip()
        )
        job_mode = (job.work_mode or "").strip().lower()
        if not preferred_modes:
            return 5, "No preferred work modes are set."
        if not job_mode:
            return 5, "Job work mode is not specified."
        if job_mode in preferred_modes:
            return 10, f"Work mode matches preference: {job.work_mode}."
        return 0, f"Work mode differs from preference: {job.work_mode}."

    def role_match(
        self,
        candidate: Candidate,
        job: Job,
    ) -> tuple[int, str]:
        preferred_roles = set(self.split_values(candidate.preferred_roles))
        job_title = job.title.strip().lower()
        if not preferred_roles:
            return 0, "No preferred roles are set."
        if any(
            role in job_title or job_title in role
            for role in preferred_roles
        ):
            return 5, f"Job title matches preferred role: {job.title}."
        return 0, f"Job title differs from preferred roles: {job.title}."

    def calculate(
        self,
        candidate: Candidate,
        job: Job,
    ) -> JobMatchResult:
        skill_score, matched, missing, skill_explanation = self.skill_match(
            candidate,
            job,
        )
        experience_score, experience_explanation = self.experience_match(
            candidate,
            job,
        )
        location_score, location_explanation = self.location_match(
            candidate,
            job,
        )
        work_mode_score, work_mode_explanation = self.work_mode_match(
            candidate,
            job,
        )
        role_score, role_explanation = self.role_match(candidate, job)

        total = (
            skill_score
            + experience_score
            + location_score
            + work_mode_score
            + role_score
        )
        explanations = [
            skill_explanation,
            experience_explanation,
            location_explanation,
            work_mode_explanation,
            role_explanation,
        ]
        return JobMatchResult(
            candidate_id=candidate.id,
            job_id=job.id,
            total_score=min(total, 100),
            skill_score=skill_score,
            experience_score=experience_score,
            location_score=location_score,
            work_mode_score=work_mode_score,
            role_score=role_score,
            matched_skills=matched,
            missing_skills=missing,
            explanation=explanations,
        )

    def rank_jobs(
        self,
        candidate: Candidate,
        jobs: Iterable[Job],
    ) -> list[JobMatchResult]:
        results = [self.calculate(candidate, job) for job in jobs]
        return sorted(
            results,
            key=lambda result: (
                result.total_score,
                len(result.matched_skills),
            ),
            reverse=True,
        )


matching_service = MatchingService()
