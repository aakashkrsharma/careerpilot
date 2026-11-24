"""Search-engine-based discovery for portals without public APIs."""
import re
import time
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlsplit

from app.models.workflow import JobDiscoveryCriteria, SourceJob
from app.services.connectors.base import BaseConnector, ConnectorError


DEFAULT_SITES = [
    "naukri.com",
    "linkedin.com/jobs",
    "instahyre.com",
    "cutshort.io",
    "hirist.tech",
    "in.indeed.com",
    "foundit.in",
    "shine.com",
    "timesjobs.com",
    "glassdoor.co.in",
    "wellfound.com",
    "weworkremotely.com",
]


class _TagStripper(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def text(self):
        return " ".join("".join(self.parts).split())


def _strip(value: str) -> str:
    parser = _TagStripper()
    parser.feed(value)
    return parser.text()


class SearchEngineConnector(BaseConnector):
    @property
    def source_name(self) -> str:
        return "search_engine"

    def discover(self, criteria: JobDiscoveryCriteria) -> list[SourceJob]:
        sites = self.config.get("sites") or DEFAULT_SITES
        if not isinstance(sites, list) or not sites:
            raise ConnectorError("Search-engine source requires a non-empty sites list.")
        query_terms = (criteria.query or " ".join(criteria.roles) or "").strip()
        locations = " ".join(criteria.locations or [])
        limit = max(1, min(criteria.limit or 20, 50))
        jobs: list[SourceJob] = []
        seen: set[str] = set()

        for site in sites:
            if len(jobs) >= limit:
                break
            query = f"site:{site} {query_terms} {locations}".strip()
            try:
                response = self.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                )
            except ConnectorError:
                continue
            html = response.text
            for href, title_html in re.findall(
                r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                html,
                re.IGNORECASE | re.DOTALL,
            ):
                if len(jobs) >= limit:
                    break
                parsed = parse_qs(urlsplit(href).query)
                actual = unquote(parsed.get("uddg", [href])[0])
                if not actual or actual in seen:
                    continue
                seen.add(actual)
                title = _strip(title_html) or "Job posting"
                domain = urlsplit(actual).netloc.replace("www.", "")
                company = domain.split(".")[0].title() if domain else "Unknown"
                job = self.make_job(
                    title=title,
                    company=company,
                    source_url=actual,
                    description=f"Discovered via search engine for {query_terms}.",
                    required_skills=query_terms,
                )
                if job is not None:
                    jobs.append(job)
            time.sleep(1.0)

        return jobs[:limit]
