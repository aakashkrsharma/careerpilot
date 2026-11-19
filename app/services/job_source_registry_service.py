"""Manage local connector configuration and source-health metadata."""
import json
import re
from typing import Optional
from urllib.parse import parse_qsl, urlsplit

from app.database.database import SessionLocal
from app.database.models import JobSource
from app.services.connectors import CONNECTOR_TYPES, DEFAULT_INTERVAL_SECONDS


REGION_GROUPS = {"india", "global_remote", "us_global"}
_SECRET_KEYS = {"api_key", "token", "password", "secret", "authorization"}


class JobSourceRegistryService:
    def get_sources(
        self,
        *,
        enabled_only: bool = False,
        source_ids: Optional[set[int]] = None,
    ) -> list[JobSource]:
        with SessionLocal() as db:
            query = db.query(JobSource)
            if enabled_only:
                query = query.filter(
                    JobSource.enabled.is_(True),
                    JobSource.terms_approved.is_(True),
                )
            if source_ids is not None:
                query = query.filter(JobSource.id.in_(source_ids))
            sources = query.order_by(JobSource.priority, JobSource.display_name).all()
            for source in sources:
                db.expunge(source)
            return sources

    def get_source(self, source_id: int) -> Optional[JobSource]:
        with SessionLocal() as db:
            source = db.query(JobSource).filter(JobSource.id == source_id).first()
            if source is not None:
                db.expunge(source)
            return source

    def register_source(
        self,
        *,
        source_key: str,
        connector_type: str,
        display_name: str,
        region_group: str,
        config: dict,
        terms_approved: bool,
        enabled: bool = False,
        priority: int = 100,
        min_interval_seconds: Optional[int] = None,
    ) -> JobSource:
        key = _normalize_source_key(source_key)
        name = display_name.strip() if isinstance(display_name, str) else ""
        if not name:
            raise ValueError("Source display name is required.")
        if connector_type not in CONNECTOR_TYPES:
            raise ValueError(f"Unsupported connector type: {connector_type}")
        if region_group not in REGION_GROUPS:
            raise ValueError("Source region group must be India, global remote, or US/global.")
        if not isinstance(config, dict):
            raise ValueError("Source configuration must be an object.")
        _validate_config(connector_type, config)
        if type(terms_approved) is not bool or type(enabled) is not bool:
            raise ValueError("Source access flags must be booleans.")
        if enabled and not terms_approved:
            raise ValueError("Review and approve the source's terms before enabling it.")
        interval = (
            DEFAULT_INTERVAL_SECONDS.get(connector_type, 3600)
            if min_interval_seconds is None
            else min_interval_seconds
        )
        if type(interval) is not int or interval < 60:
            raise ValueError("Source interval must be at least 60 seconds.")
        if connector_type == "remotive":
            interval = max(interval, 6 * 60 * 60)
        if type(priority) is not int:
            raise ValueError("Source priority must be an integer.")

        with SessionLocal.begin() as db:
            if db.query(JobSource.id).filter(JobSource.source_key == key).first():
                raise ValueError("A source with this source key is already registered.")
            if connector_type == "remotive" and db.query(JobSource.id).filter(
                JobSource.connector_type == "remotive"
            ).first():
                raise ValueError(
                    "Only one Remotive source may be registered to preserve its rate limit."
                )
            source = JobSource(
                source_key=key,
                connector_type=connector_type,
                display_name=name,
                region_group=region_group,
                config_json=json.dumps(config, sort_keys=True),
                enabled=enabled,
                terms_approved=terms_approved,
                priority=priority,
                min_interval_seconds=interval,
            )
            db.add(source)
            db.flush()
            db.expunge(source)
            return source

    def update_source_access(
        self,
        source_id: int,
        *,
        enabled: bool,
        terms_approved: bool,
    ) -> None:
        if type(enabled) is not bool or type(terms_approved) is not bool:
            raise ValueError("Source access flags must be booleans.")
        if enabled and not terms_approved:
            raise ValueError("Review and approve the source's terms before enabling it.")
        with SessionLocal.begin() as db:
            source = db.query(JobSource).filter(JobSource.id == source_id).first()
            if source is None:
                raise ValueError("Source was not found.")
            source.enabled = enabled
            source.terms_approved = terms_approved


def _normalize_source_key(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Source key is required.")
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not normalized or len(normalized) > 80:
        raise ValueError("Source key must contain 1 to 80 letters, numbers, or hyphens.")
    return normalized


def _validate_config(connector_type: str, config: dict) -> None:
    for key, value in config.items():
        if not isinstance(key, str):
            raise ValueError("Source configuration keys must be strings.")
        if key.lower() in _SECRET_KEYS:
            raise ValueError(
                "Do not store credentials in the database; use an environment variable reference."
            )
        if not isinstance(value, (str, int, float, bool, list, dict, type(None))):
            raise ValueError(f"Unsupported configuration value for {key}.")
    try:
        json.dumps(config)
    except (TypeError, ValueError) as exc:
        raise ValueError("Source configuration must be JSON serializable.") from exc

    required = {
        "greenhouse": ("board_token", "company_name"),
        "lever": ("site_name", "company_name"),
        "ashby": ("job_board_name", "company_name"),
        "smartrecruiters": ("company",),
        "rss_atom": ("feed_url",),
        "xml_feed": ("feed_url", "item_tag", "field_map"),
    }.get(connector_type, ())
    missing = [
        key
        for key in required
        if key not in config or config[key] in (None, "", {})
    ]
    if missing:
        raise ValueError(f"Missing source configuration: {', '.join(missing)}.")

    if connector_type in {"rss_atom", "xml_feed"}:
        feed_url = config.get("feed_url")
        parsed = urlsplit(feed_url) if isinstance(feed_url, str) else None
        if (
            not parsed
            or parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ValueError("Feed URLs must use HTTPS and include a hostname.")
        if any(
            _looks_sensitive(key)
            for key, _ in parse_qsl(parsed.query, keep_blank_values=True)
        ):
            raise ValueError(
                "Feed URL query parameters cannot contain credentials; "
                "use an authorized public feed URL."
            )

    if connector_type == "xml_feed" and not isinstance(config.get("field_map"), dict):
        raise ValueError("XML feed field_map must be an object.")
    if connector_type == "xml_feed":
        field_map = config["field_map"]
        missing_fields = [
            field_name
            for field_name in ("title", "company", "url")
            if not isinstance(field_map.get(field_name), str)
            or not field_map[field_name].strip()
        ]
        if missing_fields:
            raise ValueError(
                "XML field_map must include title, company, and url paths."
            )


def _looks_sensitive(value: str) -> bool:
    normalized = value.strip().lower()
    return any(
        marker in normalized
        for marker in (
            "api_key",
            "apikey",
            "access_key",
            "token",
            "secret",
            "password",
            "auth",
        )
    )


job_source_registry_service = JobSourceRegistryService()
