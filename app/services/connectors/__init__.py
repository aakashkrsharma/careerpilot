"""Registry for permitted, read-only job discovery connectors."""
from typing import Type

import httpx

from app.database.models import JobSource
from app.services.connectors.ats import (
    AshbyConnector,
    GreenhouseConnector,
    LeverConnector,
)
from app.services.connectors.base import BaseConnector, ConnectorError
from app.services.connectors.feeds import (
    RSSAtomConnector,
    WeWorkRemotelyConnector,
    XMLFeedConnector,
)
from app.services.connectors.public_apis import (
    ArbeitnowConnector,
    HimalayasConnector,
    JobicyConnector,
    RemotiveConnector,
    RemoteOKConnector,
    SmartRecruitersConnector,
    USAJobsConnector,
)
from app.services.connectors.search import SearchEngineConnector


CONNECTOR_TYPES: dict[str, Type[BaseConnector]] = {
    "greenhouse": GreenhouseConnector,
    "lever": LeverConnector,
    "ashby": AshbyConnector,
    "arbeitnow": ArbeitnowConnector,
    "jobicy": JobicyConnector,
    "remoteok": RemoteOKConnector,
    "himalayas": HimalayasConnector,
    "weworkremotely": WeWorkRemotelyConnector,
    "rss_atom": RSSAtomConnector,
    "xml_feed": XMLFeedConnector,
    "usajobs": USAJobsConnector,
    "remotive": RemotiveConnector,
    "smartrecruiters": SmartRecruitersConnector,
    "search_engine": SearchEngineConnector,
}

DEFAULT_INTERVAL_SECONDS = {
    "remotive": 6 * 60 * 60,
    "weworkremotely": 60 * 60,
    "rss_atom": 60 * 60,
    "xml_feed": 60 * 60,
}


SOURCE_TEMPLATES = (
    {
        "connector_type": "greenhouse",
        "label": "Greenhouse public board",
        "region_group": "india",
        "requires": "Board token and company name",
        "policy_url": "https://developers.greenhouse.io/job-board.html",
    },
    {
        "connector_type": "lever",
        "label": "Lever public postings",
        "region_group": "india",
        "requires": "Site name and company name",
        "policy_url": "https://github.com/Lever/postings-api",
    },
    {
        "connector_type": "ashby",
        "label": "Ashby public job board",
        "region_group": "india",
        "requires": "Job-board name and company name",
        "policy_url": "https://developers.ashbyhq.com/docs/public-job-board-api",
    },
    {
        "connector_type": "arbeitnow",
        "label": "Arbeitnow public job API",
        "region_group": "global_remote",
        "requires": "No credentials",
        "policy_url": "https://arbeitnow.com/",
    },
    {
        "connector_type": "jobicy",
        "label": "Jobicy remote jobs API",
        "region_group": "global_remote",
        "requires": "No credentials",
        "policy_url": "https://jobicy.com/api",
    },
    {
        "connector_type": "remoteok",
        "label": "Remote OK public API",
        "region_group": "global_remote",
        "requires": "No credentials",
        "policy_url": "https://remoteok.com/api",
    },
    {
        "connector_type": "himalayas",
        "label": "Himalayas public jobs API",
        "region_group": "global_remote",
        "requires": "No credentials",
        "policy_url": "https://himalayas.app/",
    },
    {
        "connector_type": "weworkremotely",
        "label": "We Work Remotely RSS",
        "region_group": "global_remote",
        "requires": "No credentials",
        "policy_url": "https://weworkremotely.com/remote-jobs.rss",
    },
    {
        "connector_type": "rss_atom",
        "label": "Authorized RSS/Atom feed",
        "region_group": "india",
        "requires": "HTTPS feed URL and, if absent from entries, company name",
        "policy_url": None,
    },
    {
        "connector_type": "xml_feed",
        "label": "Authorized mapped XML feed",
        "region_group": "india",
        "requires": "HTTPS feed URL and field mapping",
        "policy_url": None,
    },
    {
        "connector_type": "smartrecruiters",
        "label": "SmartRecruiters authorized feed",
        "region_group": "india",
        "requires": "Company slug and SMARTRECRUITERS_API_TOKEN environment variable",
        "policy_url": "https://developers.smartrecruiters.com/",
    },
    {
        "connector_type": "remotive",
        "label": "Remotive remote jobs API (opt-in)",
        "region_group": "global_remote",
        "requires": "Terms review; limited to at most four requests per day",
        "policy_url": "https://remotive.com/remote-jobs/api",
    },
    {
        "connector_type": "usajobs",
        "label": "USAJOBS API (disabled by default)",
        "region_group": "us_global",
        "requires": "API key and contact User-Agent in USAJOBS_API_KEY and USAJOBS_USER_AGENT environment variables",
        "policy_url": "https://developer.usajobs.gov/",
    },
    {
        "connector_type": "search_engine",
        "label": "Search engine (site: queries, no login)",
        "region_group": "global_remote",
        "requires": "No credentials; searches public job pages via DuckDuckGo",
        "policy_url": None,
    },
)


def create_connector(source: JobSource, client: httpx.Client) -> BaseConnector:
    connector_class = CONNECTOR_TYPES.get(source.connector_type)
    if connector_class is None:
        raise ConnectorError(f"Unsupported connector type: {source.connector_type}")
    return connector_class(source, client)
