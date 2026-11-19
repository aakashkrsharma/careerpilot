"""Public, read-only job-board APIs for employer ATS platforms."""
from typing import Any
from urllib.parse import quote

from app.database.models import JobSource
from app.models.workflow import JobDiscoveryCriteria, SourceJob
from app.services.connectors.base import BaseConnector, ConnectorError


class GreenhouseConnector(BaseConnector):
    def discover(self, criteria: JobDiscoveryCriteria) -> list[SourceJob]:
        token = _required_config(self.config, "board_token")
        company = _required_config(self.config, "company_name")
        data = self.get_json(
            f"https://boards-api.greenhouse.io/v1/boards/{quote(token, safe='')}/jobs",
            params={"content": "true"},
        )
        jobs = data.get("jobs", []) if isinstance(data, dict) else []
        results = []
        for item in jobs[: criteria.limit]:
            if not isinstance(item, dict):
                continue
            location = item.get("location")
            results.append(
                self.make_job(
                    title=item.get("title"),
                    company=company,
                    source_url=item.get("absolute_url"),
                    external_id=item.get("id"),
                    location=location.get("name") if isinstance(location, dict) else None,
                    description=item.get("content"),
                    source_updated_at=item.get("updated_at"),
                )
            )
        return [job for job in results if job is not None]


class LeverConnector(BaseConnector):
    def discover(self, criteria: JobDiscoveryCriteria) -> list[SourceJob]:
        site = _required_config(self.config, "site_name")
        company = _required_config(self.config, "company_name")
        response = self.get_json(
            f"https://api.lever.co/v0/postings/{quote(site, safe='')}",
            params={"mode": "json", "limit": min(max(criteria.limit, 1), 100)},
        )
        if not isinstance(response, list):
            raise ConnectorError("Lever returned an unexpected response shape.")
        results = []
        for item in response[: criteria.limit]:
            if not isinstance(item, dict):
                continue
            categories = item.get("categories")
            categories = categories if isinstance(categories, dict) else {}
            results.append(
                self.make_job(
                    title=item.get("text"),
                    company=company,
                    source_url=item.get("hostedUrl") or item.get("applyUrl"),
                    external_id=item.get("id"),
                    location=categories.get("location"),
                    work_mode=categories.get("workplaceType"),
                    description=item.get("descriptionPlain") or item.get("description"),
                    posted_at=item.get("createdAt"),
                )
            )
        return [job for job in results if job is not None]


class AshbyConnector(BaseConnector):
    def discover(self, criteria: JobDiscoveryCriteria) -> list[SourceJob]:
        board = _required_config(self.config, "job_board_name")
        company = _required_config(self.config, "company_name")
        data = self.get_json(
            f"https://api.ashbyhq.com/posting-api/job-board/{quote(board, safe='')}",
            params={"includeCompensation": "true"},
        )
        jobs = data.get("jobs", []) if isinstance(data, dict) else []
        results = []
        for item in jobs[: criteria.limit]:
            if not isinstance(item, dict):
                continue
            compensation = (
                item.get("compensation")
                or item.get("compensationTierSummary")
                or item.get("compensationText")
            )
            location = item.get("location")
            if isinstance(location, dict):
                location = location.get("name") or location.get("locationName")
            if isinstance(compensation, dict):
                compensation = (
                    compensation.get("summary")
                    or compensation.get("description")
                    or compensation.get("text")
                )
            remote = item.get("isRemote")
            work_mode = "remote" if remote is True else None
            results.append(
                self.make_job(
                    title=item.get("title"),
                    company=company,
                    source_url=item.get("jobUrl") or item.get("applyUrl"),
                    external_id=item.get("id"),
                    location=location,
                    work_mode=work_mode,
                    description=item.get("descriptionHtml") or item.get("description"),
                    posted_at=item.get("publishedAt"),
                    salary=compensation,
                )
            )
        return [job for job in results if job is not None]


def _required_config(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConnectorError(f"Connector configuration is missing {key}.")
    return value.strip()
