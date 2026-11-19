"""Adapters for public job APIs with no browser automation or authentication bypass."""
import os
from typing import Any
from urllib.parse import quote

from app.models.workflow import JobDiscoveryCriteria, SourceJob
from app.services.connectors.base import BaseConnector, ConnectorError


class ArbeitnowConnector(BaseConnector):
    def discover(self, criteria: JobDiscoveryCriteria) -> list[SourceJob]:
        data = self.get_json("https://www.arbeitnow.com/api/job-board-api")
        items = data.get("data", []) if isinstance(data, dict) else []
        results = []
        for item in items[: criteria.limit]:
            if not isinstance(item, dict):
                continue
            tags = item.get("tags")
            results.append(
                self.make_job(
                    title=item.get("title"),
                    company=item.get("company_name"),
                    source_url=item.get("url"),
                    external_id=item.get("slug") or item.get("id"),
                    location=item.get("location"),
                    work_mode="remote" if item.get("remote") else None,
                    description=item.get("description"),
                    required_skills=", ".join(tags) if isinstance(tags, list) else tags,
                    posted_at=item.get("created_at"),
                )
            )
        return [job for job in results if job is not None]


class JobicyConnector(BaseConnector):
    def discover(self, criteria: JobDiscoveryCriteria) -> list[SourceJob]:
        params: dict[str, Any] = {"count": min(max(criteria.limit, 1), 50)}
        if criteria.india_first:
            params["geo"] = "india"
        if criteria.query:
            params["tag"] = criteria.query[:100]
        data = self.get_json("https://jobicy.com/api/v2/remote-jobs", params=params)
        items = data.get("jobs", []) if isinstance(data, dict) else []
        results = []
        for item in items[: criteria.limit]:
            if not isinstance(item, dict):
                continue
            results.append(
                self.make_job(
                    title=item.get("jobTitle"),
                    company=item.get("companyName"),
                    source_url=item.get("url"),
                    external_id=item.get("id"),
                    location=item.get("jobGeo"),
                    work_mode="remote",
                    description=item.get("jobDescription"),
                    posted_at=item.get("pubDate"),
                    salary=item.get("annualSalary") or item.get("salary"),
                    currency=item.get("salaryCurrency"),
                    period="annual" if item.get("annualSalary") else None,
                )
            )
        return [job for job in results if job is not None]


class RemoteOKConnector(BaseConnector):
    def discover(self, criteria: JobDiscoveryCriteria) -> list[SourceJob]:
        data = self.get_json("https://remoteok.com/api")
        if not isinstance(data, list):
            raise ConnectorError("Remote OK returned an unexpected response shape.")
        results = []
        for item in data:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            tags = item.get("tags")
            results.append(
                self.make_job(
                    title=item.get("position"),
                    company=item.get("company"),
                    source_url=item.get("url"),
                    external_id=item.get("id"),
                    location=item.get("location"),
                    work_mode="remote",
                    description=item.get("description"),
                    required_skills=", ".join(tags) if isinstance(tags, list) else None,
                    posted_at=item.get("date"),
                    salary=item.get("salary"),
                )
            )
            if len(results) >= criteria.limit:
                break
        return [job for job in results if job is not None]


class HimalayasConnector(BaseConnector):
    def discover(self, criteria: JobDiscoveryCriteria) -> list[SourceJob]:
        data = self.get_json(
            "https://himalayas.app/jobs/api",
            params={"limit": min(max(criteria.limit, 1), 100)},
        )
        items = data.get("jobs", []) if isinstance(data, dict) else []
        results = []
        for item in items[: criteria.limit]:
            if not isinstance(item, dict):
                continue
            restrictions = item.get("locationRestrictions")
            if isinstance(restrictions, list):
                location = ", ".join(
                    str(value).strip()
                    for value in restrictions
                    if str(value).strip()
                )
            else:
                location = restrictions or item.get("location")
            results.append(
                self.make_job(
                    title=item.get("title"),
                    company=item.get("companyName"),
                    source_url=item.get("applicationLink") or item.get("url"),
                    external_id=item.get("id"),
                    location=location,
                    work_mode="remote",
                    description=item.get("description"),
                    posted_at=item.get("pubDate") or item.get("publishedAt"),
                    salary_min=item.get("minSalary"),
                    salary_max=item.get("maxSalary"),
                    currency=item.get("currency"),
                    period=item.get("salaryPeriod"),
                )
            )
        return [job for job in results if job is not None]


class USAJobsConnector(BaseConnector):
    def discover(self, criteria: JobDiscoveryCriteria) -> list[SourceJob]:
        key_name = self.config.get("api_key_env", "USAJOBS_API_KEY")
        api_key = os.getenv(key_name)
        if not api_key:
            raise ConnectorError(
                f"USAJOBS requires an API key in the {key_name} environment variable."
            )
        user_agent_env = self.config.get("user_agent_env", "USAJOBS_USER_AGENT")
        user_agent = os.getenv(user_agent_env)
        if not user_agent:
            raise ConnectorError(
                "USAJOBS requires a contact User-Agent in the "
                f"{user_agent_env} environment variable."
            )
        params: dict[str, Any] = {
            "ResultsPerPage": min(max(criteria.limit, 1), 100),
        }
        if criteria.query:
            params["Keyword"] = criteria.query[:100]
        if criteria.locations:
            params["LocationName"] = ", ".join(criteria.locations)
        data = self.get_json(
            "https://data.usajobs.gov/api/Search",
            params=params,
            headers={
                "Authorization-Key": api_key,
                "User-Agent": user_agent,
            },
        )
        items = (
            data.get("SearchResult", {}).get("SearchResultItems", [])
            if isinstance(data, dict)
            else []
        )
        results = []
        for item in items[: criteria.limit]:
            if not isinstance(item, dict):
                continue
            descriptor = item.get("MatchedObjectDescriptor")
            if not isinstance(descriptor, dict):
                continue
            user_area = descriptor.get("UserArea")
            details = user_area.get("Details") if isinstance(user_area, dict) else {}
            details = details if isinstance(details, dict) else {}
            locations = descriptor.get("PositionLocation")
            location = (
                ", ".join(
                    str(place.get("LocationName", "")).strip()
                    for place in locations
                    if isinstance(place, dict) and place.get("LocationName")
                )
                if isinstance(locations, list)
                else descriptor.get("PositionLocationDisplay")
            )
            compensation = descriptor.get("PositionRemuneration")
            salary_min = salary_max = currency = period = None
            if isinstance(compensation, list) and compensation:
                pay = compensation[0]
                if isinstance(pay, dict):
                    salary_min = pay.get("MinimumRange")
                    salary_max = pay.get("MaximumRange")
                    currency = pay.get("CurrencyCode")
                    period = pay.get("RateIntervalCode")
            results.append(
                self.make_job(
                    title=descriptor.get("PositionTitle"),
                    company=descriptor.get("OrganizationName"),
                    source_url=descriptor.get("PositionURI"),
                    external_id=item.get("MatchedObjectId"),
                    location=location,
                    description=details.get("JobSummary"),
                    posted_at=descriptor.get("PublicationStartDate"),
                    salary_min=salary_min,
                    salary_max=salary_max,
                    currency=currency,
                    period=period,
                )
            )
        return [job for job in results if job is not None]


class RemotiveConnector(BaseConnector):
    """Optional adapter. Registration must explicitly record terms approval."""

    def discover(self, criteria: JobDiscoveryCriteria) -> list[SourceJob]:
        params: dict[str, Any] = {"limit": min(max(criteria.limit, 1), 50)}
        if criteria.query:
            params["search"] = criteria.query[:100]
        data = self.get_json("https://remotive.com/api/remote-jobs", params=params)
        items = data.get("jobs", []) if isinstance(data, dict) else []
        results = []
        for item in items[: criteria.limit]:
            if not isinstance(item, dict):
                continue
            results.append(
                self.make_job(
                    title=item.get("title"),
                    company=item.get("company_name"),
                    source_url=item.get("url"),
                    external_id=item.get("id"),
                    location=item.get("candidate_required_location"),
                    work_mode="remote",
                    description=item.get("description"),
                    required_skills=item.get("tags"),
                    posted_at=item.get("publication_date"),
                    salary=item.get("salary"),
                )
            )
        return [job for job in results if job is not None]


class SmartRecruitersConnector(BaseConnector):
    def discover(self, criteria: JobDiscoveryCriteria) -> list[SourceJob]:
        company = self.config.get("company")
        if not isinstance(company, str) or not company.strip():
            raise ConnectorError("SmartRecruiters configuration requires company.")
        token_env = self.config.get("token_env", "SMARTRECRUITERS_API_TOKEN")
        token = os.getenv(token_env)
        if not token:
            raise ConnectorError(
                f"SmartRecruiters requires a token in the {token_env} environment variable."
            )
        data = self.get_json(
            f"https://api.smartrecruiters.com/v1/companies/{quote(company.strip(), safe='')}/postings",
            params={"limit": min(max(criteria.limit, 1), 100)},
            headers={"X-SmartToken": token},
        )
        items = data.get("content", []) if isinstance(data, dict) else []
        results = []
        for item in items[: criteria.limit]:
            if not isinstance(item, dict):
                continue
            location_data = item.get("location")
            location = (
                ", ".join(
                    str(location_data.get(key)).strip()
                    for key in ("city", "region", "country")
                    if location_data.get(key)
                )
                if isinstance(location_data, dict)
                else None
            )
            results.append(
                self.make_job(
                    title=item.get("name"),
                    company=company,
                    source_url=item.get("ref"),
                    external_id=item.get("id"),
                    location=location,
                    posted_at=item.get("releasedDate"),
                )
            )
        return [job for job in results if job is not None]
