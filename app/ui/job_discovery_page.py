"""Compliant multi-source discovery controls and source-health view."""
import json
from datetime import datetime

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from app.services.candidate_service import candidate_service
from app.services.connectors import SOURCE_TEMPLATES
from app.services.job_discovery_service import job_discovery_service
from app.services.job_source_registry_service import (
    REGION_GROUPS,
    job_source_registry_service,
)
from app.models.workflow import JobDiscoveryCriteria


INDIA_DEFAULT_LOCATIONS = (
    "Bengaluru",
    "Hyderabad",
    "Pune",
    "Delhi NCR",
    "Mumbai",
    "Chennai",
    "India - Remote",
)


QUICK_START_SOURCES = [
    ("arbeitnow", "arbeitnow-1", "Arbeitnow Public Jobs", "global_remote", {}),
    ("jobicy", "jobicy-1", "Jobicy Public Jobs", "global_remote", {}),
    ("remoteok", "remoteok-1", "Remote OK Public Jobs", "global_remote", {}),
    ("himalayas", "himalayas-1", "Himalayas Public Jobs", "global_remote", {}),
    ("weworkremotely", "weworkremotely-1", "We Work Remotely RSS", "global_remote", {}),
    (
        "search_engine",
        "search-engine-1",
        "Search Engine Portal Discovery",
        "global_remote",
        {
            "sites": [
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
            ]
        },
    ),
]


def show_job_discovery_page() -> None:
    st.header("Discover Jobs")
    st.caption(
        "Connectors use public or explicitly authorized read-only feeds. "
        "Only the search terms and locations you enter are sent to a source; "
        "candidate identity, resume content, and answer-bank data stay local."
    )

    if st.button("Quick start: enable recommended public sources (no login)"):
        created = 0
        skipped = 0
        for connector_type, key, name, region, config in QUICK_START_SOURCES:
            try:
                job_source_registry_service.register_source(
                    source_key=key,
                    connector_type=connector_type,
                    display_name=name,
                    region_group=region,
                    config=config,
                    terms_approved=True,
                    enabled=True,
                    priority=100,
                )
                created += 1
            except ValueError:
                skipped += 1
        st.success(
            f"Quick start complete: {created} source(s) added, "
            f"{skipped} already present."
        )
        st.rerun()

    _show_source_registration()
    candidates = candidate_service.get_all_candidates()
    if not candidates:
        _show_source_health()
        st.info("Create a candidate profile before running job discovery.")
        return

    candidate_labels = {
        f"{candidate.full_name} ({candidate.email})": candidate.id
        for candidate in candidates
    }
    selected_label = st.selectbox(
        "Candidate for cooldown and matching context",
        options=list(candidate_labels),
        key="discovery_candidate",
    )
    candidate = candidate_service.get_candidate_by_id(candidate_labels[selected_label])

    with st.form("job_discovery_run_form"):
        st.subheader("Search criteria")
        role_terms = st.text_input(
            "Role/search terms (shared with selected sources)",
            value=(candidate.preferred_roles or "") if candidate else "",
            help="Use role titles only; resume text, name, and email are never sent.",
        )
        default_locations = (
            candidate.preferred_locations
            if candidate and candidate.preferred_locations
            else ", ".join(INDIA_DEFAULT_LOCATIONS)
        )
        locations_text = st.text_input(
            "Locations",
            value=default_locations,
            help="Comma-separated locations. India and APAC eligibility is enforced by default.",
        )
        india_first = st.checkbox(
            "Only include listings explicitly eligible in India/APAC",
            value=True,
        )
        limit = st.slider("Maximum listings per source", 1, 100, 50)
        sources = job_source_registry_service.get_sources(enabled_only=True)
        source_labels = {
            f"{source.display_name} [{source.source_key}]": source.id
            for source in sources
        }
        selected_sources = st.multiselect(
            "Sources to run (blank means all enabled and due sources)",
            options=list(source_labels),
            key="discovery_sources",
        )
        run_requested = st.form_submit_button(
            "Discover Jobs",
            disabled=not sources,
            type="primary",
        )

    if run_requested:
        locations = tuple(
            location.strip()
            for location in locations_text.split(",")
            if location.strip()
        )
        criteria = JobDiscoveryCriteria(
            query=role_terms.strip() or None,
            roles=tuple(
                role.strip()
                for role in (candidate.preferred_roles or "").split(",")
                if role.strip()
            )
            if candidate
            else (),
            locations=locations,
            limit=limit,
            india_first=india_first,
        )
        selected_ids = (
            {source_labels[label] for label in selected_sources}
            if selected_sources
            else None
        )
        progress_total = len(selected_sources) or len(sources)
        progress = st.progress(0.0, text="Preparing source run...")
        completed_sources = []

        def update_progress(result):
            completed_sources.append(result)
            progress.progress(
                min(len(completed_sources) / max(progress_total, 1), 1.0),
                text=f"Checked {result.display_name}: {result.status}",
            )

        try:
            with st.spinner("Querying enabled, due sources..."):
                result = job_discovery_service.run(
                    candidate.id,
                    criteria,
                    source_ids=selected_ids,
                    progress_callback=update_progress,
                )
            progress.progress(1.0, text="Discovery run complete.")
            if result.source_results:
                _show_run_results(result.source_results)
            else:
                st.info(
                    "No eligible sources were registered. Add a source and approve its terms first."
                )
        except (ValueError, RuntimeError, SQLAlchemyError) as exc:
            st.error(f"Could not run discovery: {exc}")

    _show_source_health()


def _show_source_registration() -> None:
    st.subheader("Source setup")
    templates_by_type = {
        template["connector_type"]: template for template in SOURCE_TEMPLATES
    }
    connector_type = st.selectbox(
        "Source type",
        options=list(templates_by_type),
        format_func=lambda value: templates_by_type[value]["label"],
        key="discovery_source_type",
    )
    template = templates_by_type[connector_type]

    with st.expander("Register a source", expanded=False):
        if template["policy_url"]:
            st.link_button("Review source documentation / terms", template["policy_url"])
        st.caption(template["requires"])
        with st.form("register_job_source_form"):
            display_name = st.text_input(
                "Display name",
                value=template["label"],
            )
            config = _source_config_fields(connector_type)
            region_group = st.selectbox(
                "Source group",
                options=sorted(REGION_GROUPS),
                index=sorted(REGION_GROUPS).index(template["region_group"]),
                format_func=_region_label,
            )
            existing = job_source_registry_service.get_sources()
            next_number = 1 + sum(
                source.connector_type == connector_type for source in existing
            )
            source_key = st.text_input(
                "Unique source key",
                value=f"{connector_type}-{next_number}",
                help="Use a distinct key for each company board or feed.",
            )
            priority = st.number_input("Priority (lower runs first)", 0, 1000, 100)
            terms_approved = st.checkbox(
                "I reviewed this source's terms, have permission to use the feed/API, "
                "and will retain its required attribution.",
                value=False,
            )
            enabled = st.checkbox(
                "Enable after registration",
                value=False,
                help="USAJOBS and Remotive are opt-in. Credentials belong in environment variables, not here.",
            )
            submitted = st.form_submit_button("Register source")
            if submitted:
                try:
                    job_source_registry_service.register_source(
                        source_key=source_key,
                        connector_type=connector_type,
                        display_name=display_name,
                        region_group=region_group,
                        config=config,
                        terms_approved=terms_approved,
                        enabled=enabled,
                        priority=int(priority),
                    )
                    st.success("Source registered.")
                    st.rerun()
                except (ValueError, TypeError, json.JSONDecodeError) as exc:
                    st.error(f"Could not register source: {exc}")


def _source_config_fields(connector_type: str) -> dict:
    if connector_type == "greenhouse":
        return {
            "company_name": st.text_input("Company name"),
            "board_token": st.text_input("Greenhouse board token"),
        }
    if connector_type == "lever":
        return {
            "company_name": st.text_input("Company name"),
            "site_name": st.text_input("Lever site name"),
        }
    if connector_type == "ashby":
        return {
            "company_name": st.text_input("Company name"),
            "job_board_name": st.text_input("Ashby job-board name"),
        }
    if connector_type == "smartrecruiters":
        return {
            "company": st.text_input("SmartRecruiters company slug"),
            "token_env": st.text_input(
                "Token environment variable",
                value="SMARTRECRUITERS_API_TOKEN",
            ),
        }
    if connector_type == "rss_atom":
        return {
            "feed_url": st.text_input("HTTPS RSS/Atom feed URL"),
            "company_name": st.text_input(
                "Fallback company name if entries omit the employer"
            ),
        }
    if connector_type == "xml_feed":
        item_tag = st.text_input("XML job item tag", value="job")
        field_map = st.text_area(
            "XML field map (JSON)",
            value=json.dumps(
                {
                    "title": "title",
                    "company": "company",
                    "url": "url",
                    "external_id": "id",
                    "location": "location",
                    "description": "description",
                    "posted_at": "posted_at",
                    "salary": "salary",
                },
                indent=2,
            ),
        )
        try:
            parsed_field_map = json.loads(field_map)
        except json.JSONDecodeError:
            parsed_field_map = None
        return {
            "feed_url": st.text_input("HTTPS XML feed URL"),
            "item_tag": item_tag,
            "field_map": parsed_field_map,
        }
    if connector_type == "usajobs":
        return {
            "api_key_env": st.text_input(
                "API key environment variable",
                value="USAJOBS_API_KEY",
            ),
            "user_agent_env": st.text_input(
                "Contact User-Agent environment variable",
                value="USAJOBS_USER_AGENT",
            ),
        }
    return {}


def _show_source_health() -> None:
    sources = job_source_registry_service.get_sources()
    st.subheader("Source health")
    if not sources:
        st.info("No sources registered yet.")
        return
    rows = []
    for source in sources:
        rows.append(
            {
                "Source": source.display_name,
                "Key": source.source_key,
                "Type": source.connector_type,
                "Group": _region_label(source.region_group),
                "Enabled": source.enabled,
                "Terms approved": source.terms_approved,
                "Status": source.last_status,
                "Last run (UTC)": _format_datetime(source.last_run_at),
                "Next allowed (UTC)": _format_datetime(source.next_allowed_at),
                "Fetched": source.last_fetched_count,
                "New": source.last_created_count,
                "Updated": source.last_updated_count,
                "Existing": source.last_duplicate_count,
                "Cooldown blocked": source.last_cooldown_count,
                "Excluded by India filter": source.last_excluded_region_count,
                "Error": source.last_error or "",
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)

    with st.expander("Manage source access"):
        for source in sources:
            with st.form(f"manage_source_{source.id}"):
                st.write(f"**{source.display_name}** (`{source.source_key}`)")
                enabled = st.checkbox(
                    "Enabled",
                    value=source.enabled,
                    key=f"source_enabled_{source.id}",
                )
                terms_approved = st.checkbox(
                    "Terms reviewed and approved",
                    value=source.terms_approved,
                    key=f"source_terms_{source.id}",
                )
                if st.form_submit_button("Save source access"):
                    try:
                        job_source_registry_service.update_source_access(
                            source.id,
                            enabled=enabled,
                            terms_approved=terms_approved,
                        )
                        st.success("Source access updated.")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))


def _show_run_results(results) -> None:
    st.subheader("Discovery run results")
    for result in results:
        with st.container(border=True):
            st.write(f"**{result.display_name}:** {result.status}")
            if result.status == "failed":
                st.error(result.error_message or "Source failed.")
            elif result.status == "rate_limited":
                st.info("Skipped because the source's minimum interval has not elapsed.")
            st.write(
                f"Fetched {result.fetched_count} · New {result.created_count} · "
                f"Updated {result.updated_count} · Existing {result.duplicate_count} · "
                f"Cooldown blocked {result.cooldown_count} · "
                f"Excluded by India/APAC filter {result.excluded_region_count}"
            )


def _region_label(value: str) -> str:
    return {
        "india": "India-focused",
        "global_remote": "Global remote (India/APAC filtered by default)",
        "us_global": "US/other global (disabled by default)",
    }.get(value, value)


def _format_datetime(value: datetime | None) -> str:
    return value.isoformat(timespec="seconds") if value else ""
