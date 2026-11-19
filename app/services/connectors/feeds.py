"""RSS/Atom and mapped XML feed connectors."""
from typing import Optional
from xml.etree import ElementTree

from app.models.workflow import JobDiscoveryCriteria, SourceJob
from app.services.connectors.base import (
    BaseConnector,
    ConnectorError,
    xml_child_text,
    xml_local_name,
)


class RSSAtomConnector(BaseConnector):
    def discover(self, criteria: JobDiscoveryCriteria) -> list[SourceJob]:
        feed_url = self.config.get("feed_url")
        if not isinstance(feed_url, str) or not feed_url.strip():
            raise ConnectorError("RSS/Atom configuration requires feed_url.")
        return self._parse_feed(feed_url.strip(), criteria.limit, wework=False)

    def _parse_feed(
        self,
        feed_url: str,
        limit: int,
        *,
        wework: bool,
    ) -> list[SourceJob]:
        response = self.get(feed_url)
        _reject_xml_entities(response.content)
        try:
            root = ElementTree.fromstring(response.content)
        except ElementTree.ParseError as exc:
            raise ConnectorError("Feed returned invalid XML.") from exc

        entries = [
            element
            for element in root.iter()
            if xml_local_name(element) in {"item", "entry"}
        ]
        results = []
        configured_company = self.config.get("company_name")
        for item in entries[:limit]:
            title = xml_child_text(item, "title")
            company = xml_child_text(item, "company", "employer")
            if not company and isinstance(configured_company, str):
                company = configured_company.strip() or None
            if wework and title and not company and ":" in title:
                company, title = title.split(":", 1)
                company = company.strip() or None
                title = title.strip()
            link = _feed_link(item)
            results.append(
                self.make_job(
                    title=title,
                    company=company,
                    source_url=link,
                    external_id=xml_child_text(item, "guid", "id"),
                    location=xml_child_text(item, "location", "region", "country"),
                    work_mode=xml_child_text(item, "work_mode", "workplace"),
                    description=xml_child_text(
                        item, "description", "summary", "content", "encoded"
                    ),
                    required_skills=xml_child_text(item, "skills"),
                    posted_at=xml_child_text(
                        item, "pubdate", "published", "updated", "date"
                    ),
                    salary=xml_child_text(item, "salary", "compensation"),
                )
            )
        return [job for job in results if job is not None]


class WeWorkRemotelyConnector(RSSAtomConnector):
    def discover(self, criteria: JobDiscoveryCriteria) -> list[SourceJob]:
        return self._parse_feed(
            "https://weworkremotely.com/remote-jobs.rss",
            criteria.limit,
            wework=True,
        )


class XMLFeedConnector(BaseConnector):
    def discover(self, criteria: JobDiscoveryCriteria) -> list[SourceJob]:
        feed_url = self.config.get("feed_url")
        item_tag = self.config.get("item_tag", "job")
        field_map = self.config.get("field_map", {})
        if not isinstance(feed_url, str) or not feed_url.strip():
            raise ConnectorError("XML feed configuration requires feed_url.")
        if not isinstance(item_tag, str) or not item_tag.strip():
            raise ConnectorError("XML feed item_tag must be a non-empty string.")
        if not isinstance(field_map, dict):
            raise ConnectorError("XML feed field_map must be an object.")

        response = self.get(feed_url.strip())
        _reject_xml_entities(response.content)
        try:
            root = ElementTree.fromstring(response.content)
        except ElementTree.ParseError as exc:
            raise ConnectorError("Feed returned invalid XML.") from exc
        items = [
            element
            for element in root.iter()
            if xml_local_name(element) == item_tag.strip().lower()
        ]
        results = []
        for item in items[: criteria.limit]:
            values = {
                key: _mapped_value(item, field_map.get(key))
                for key in (
                    "title",
                    "company",
                    "url",
                    "external_id",
                    "location",
                    "work_mode",
                    "description",
                    "skills",
                    "posted_at",
                    "salary",
                    "currency",
                    "period",
                )
            }
            results.append(
                self.make_job(
                    title=values["title"],
                    company=values["company"],
                    source_url=values["url"],
                    external_id=values["external_id"],
                    location=values["location"],
                    work_mode=values["work_mode"],
                    description=values["description"],
                    required_skills=values["skills"],
                    posted_at=values["posted_at"],
                    salary=values["salary"],
                    currency=values["currency"],
                    period=values["period"],
                )
            )
        return [job for job in results if job is not None]


def _feed_link(item: ElementTree.Element) -> Optional[str]:
    for element in item.iter():
        if xml_local_name(element) != "link":
            continue
        href = element.attrib.get("href")
        text = (element.text or "").strip()
        if href:
            return href
        if text:
            return text
    return xml_child_text(item, "url")


def _mapped_value(item: ElementTree.Element, path: object) -> Optional[str]:
    if not isinstance(path, str) or not path.strip():
        return None
    current = [item]
    for part in path.strip().lstrip("./").split("/"):
        if not part or part == ".":
            continue
        next_elements = []
        for element in current:
            next_elements.extend(
                child
                for child in list(element)
                if xml_local_name(child) == part.lower()
            )
        current = next_elements
    if not current:
        return None
    value = "".join(current[0].itertext()).strip()
    return value or None


def _reject_xml_entities(payload: bytes) -> None:
    upper_payload = payload.upper()
    if b"<!DOCTYPE" in upper_payload or b"<!ENTITY" in upper_payload:
        raise ConnectorError("XML DTD and entity declarations are not allowed.")
