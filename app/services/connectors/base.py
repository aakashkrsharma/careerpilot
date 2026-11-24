"""Shared HTTP, parsing, and normalization helpers for source adapters."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import ipaddress
import json
import socket
from typing import Any, Optional
from urllib.parse import urlsplit
from xml.etree import ElementTree

import httpx

from app.database.models import JobSource
from app.models.workflow import JobDiscoveryCriteria, SourceJob
from app.services.salary_parser import parse_compensation


MAX_RESPONSE_BYTES = 5 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 12.0
USER_AGENT = "CareerPilot local job discovery (respecting source terms)"


class ConnectorError(RuntimeError):
    """A source request or response could not be processed safely."""

    def __init__(self, message: str, *, retry_after_seconds: Optional[int] = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class BaseConnector:
    def __init__(self, source: JobSource, client: httpx.Client):
        self.source = source
        self.client = client
        self.config = json.loads(source.config_json or "{}")

    @property
    def source_name(self) -> str:
        return self.source.connector_type

    def discover(self, criteria: JobDiscoveryCriteria) -> list[SourceJob]:
        raise NotImplementedError

    def get(self, url: str, *, params: Optional[dict] = None, headers: Optional[dict] = None):
        _validate_public_http_url(url)
        request_headers = {"User-Agent": USER_AGENT}
        request_headers.update(headers or {})
        try:
            with self.client.stream(
                "GET",
                url,
                params=params,
                headers=request_headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
                follow_redirects=False,
            ) as response:
                if 300 <= response.status_code < 400:
                    raise ConnectorError(
                        "Source redirected the request; redirects are disabled."
                    )
                if response.status_code == 429:
                    raise _rate_limit_error(response.headers.get("Retry-After"))
                if response.status_code >= 400:
                    raise ConnectorError(
                        f"Source returned HTTP {response.status_code}."
                    )
                payload = bytearray()
                for chunk in response.iter_bytes(chunk_size=64 * 1024):
                    payload.extend(chunk)
                    if len(payload) > MAX_RESPONSE_BYTES:
                        raise ConnectorError("Source response exceeded the 5 MiB limit.")
                headers = dict(response.headers)
                headers.pop("content-encoding", None)
                headers.pop("content-length", None)
                result = httpx.Response(
                    status_code=response.status_code,
                    headers=headers,
                    content=bytes(payload),
                    request=httpx.Request("GET", url),
                )
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"Request failed ({type(exc).__name__})."
            ) from exc
        return result

    def get_json(self, url: str, *, params: Optional[dict] = None, headers: Optional[dict] = None):
        response = self.get(url, params=params, headers=headers)
        try:
            return response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise ConnectorError("Source returned invalid JSON.") from exc

    def text(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        clean = str(value).strip()
        return clean or None

    def make_job(
        self,
        *,
        title: Any,
        company: Any,
        source_url: Any,
        external_id: Any = None,
        location: Any = None,
        work_mode: Any = None,
        description: Any = None,
        required_skills: Any = None,
        posted_at: Any = None,
        source_updated_at: Any = None,
        salary: Any = None,
        salary_min: Any = None,
        salary_max: Any = None,
        currency: Any = None,
        period: Any = None,
    ) -> Optional[SourceJob]:
        clean_title = self.text(title)
        clean_company = self.text(company)
        if not clean_title or not clean_company:
            return None
        salary_text = self.text(salary)
        compensation = parse_compensation(
            salary_text,
            currency_hint=self.text(currency),
            period_hint=self.text(period),
        )
        minimum = _safe_int(salary_min)
        maximum = _safe_int(salary_max)
        if minimum is None:
            minimum = compensation.minimum
        if maximum is None:
            maximum = compensation.maximum
        if minimum is not None and maximum is not None and minimum > maximum:
            minimum, maximum = maximum, minimum
        return SourceJob(
            source=self.source.connector_type,
            title=clean_title,
            company=clean_company,
            source_url=self.text(source_url),
            source_external_id=self.text(external_id),
            location=self.text(location),
            work_mode=self.text(work_mode),
            description=strip_markup(description),
            posted_at=parse_datetime(posted_at),
            source_updated_at=parse_datetime(source_updated_at),
            required_skills=self.text(required_skills),
            salary_min=minimum,
            salary_max=maximum,
            salary_currency=compensation.currency or self.text(currency),
            salary_period=compensation.period or self.text(period),
            salary_text=salary_text,
        )


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        clean = data.strip()
        if clean:
            self.parts.append(clean)


def strip_markup(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    parser = _TextExtractor()
    parser.feed(text)
    parser.close()
    return " ".join(parser.parts) or text


def parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        try:
            parsed = datetime.fromtimestamp(value / 1000 if value > 10**12 else value, timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    else:
        candidate = str(value).strip()
        if not candidate:
            return None
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except ValueError:
            try:
                from email.utils import parsedate_to_datetime

                parsed = parsedate_to_datetime(candidate)
            except (TypeError, ValueError, OverflowError):
                return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def xml_local_name(element: ElementTree.Element) -> str:
    return element.tag.rsplit("}", 1)[-1].lower()


def xml_child_text(element: ElementTree.Element, *names: str) -> Optional[str]:
    wanted = {name.lower() for name in names}
    for child in element.iter():
        if child is element or xml_local_name(child) not in wanted:
            continue
        value = "".join(child.itertext()).strip()
        if value:
            return value
    return None


def _safe_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        parsed = int(float(value))
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if parsed >= 0 else None


def _rate_limit_error(retry_after: Optional[str]) -> ConnectorError:
    suffix = f" Retry after {retry_after}." if retry_after else ""
    try:
        retry_after_seconds = int(retry_after) if retry_after else None
    except ValueError:
        try:
            retry_after_time = parsedate_to_datetime(retry_after)
            retry_after_seconds = max(
                0,
                int((retry_after_time - datetime.now(timezone.utc)).total_seconds()),
            )
        except (TypeError, ValueError, OverflowError):
            retry_after_seconds = None
    return ConnectorError(
        f"Source rate-limited the request.{suffix}",
        retry_after_seconds=retry_after_seconds,
    )


def _validate_public_http_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ConnectorError("Source URLs must use HTTPS and include a hostname.")
    hostname = parsed.hostname.lower()
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".local"):
        raise ConnectorError("Local and private-network source URLs are not allowed.")
    try:
        addresses = {
            entry[4][0]
            for entry in socket.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM)
        }
    except OSError as exc:
        raise ConnectorError(f"Could not resolve source host {hostname}.") from exc
    if not addresses:
        raise ConnectorError("Source hostname did not resolve to a public address.")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ConnectorError("Local and private-network source URLs are not allowed.")
