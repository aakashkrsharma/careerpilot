"""Manual job discovery, storage, filtering, and duplicate prevention page."""
from sqlalchemy.exc import SQLAlchemyError
import streamlit as st

from app.services.candidate_service import candidate_service
from app.services.job_service import job_service
from app.services.matching_service import matching_service


def show_jobs_page():
    st.header("Jobs")

    candidates = candidate_service.get_all_candidates()
    candidate = None
    if candidates:
        candidate_options = {
            f"{item.full_name} ({item.email})": item.id
            for item in candidates
        }
        selected_candidate = st.selectbox(
            "Candidate for preference filtering",
            options=list(candidate_options.keys()),
            key="jobs_candidate",
        )
        candidate = candidate_service.get_candidate_by_id(
            candidate_options[selected_candidate]
        )

    with st.expander("Import Job from Public URL", expanded=False):
        with st.form("import_job_url_form"):
            import_url = st.text_input("Public job posting URL")
            if st.form_submit_button("Import Job"):
                try:
                    job = job_service.import_job_from_url(import_url)
                    st.success(f"Imported job: {job.title} at {job.company}")
                except (ValueError, Exception) as exc:
                    st.error(f"Could not import job: {exc}")

    with st.expander("Add a Job", expanded=False):
        with st.form("add_job_form"):
            title = st.text_input("Job Title")
            company = st.text_input("Company")
            source = st.text_input("Source", value="manual")
            source_url = st.text_input("Source URL")
            location = st.text_input("Location")
            work_mode = st.selectbox(
                "Work Mode",
                options=["", "Remote", "Hybrid", "On-site"],
            )
            description = st.text_area("Job Description", height=200)
            required_skills = st.text_input(
                "Required Skills",
                help="Enter comma-separated skills.",
            )
            col1, col2, col3 = st.columns(3)
            with col1:
                minimum_experience = st.number_input(
                    "Minimum Experience",
                    min_value=0,
                    step=1,
                    value=0,
                )
            with col2:
                salary_min = st.number_input(
                    "Salary Min",
                    min_value=0,
                    step=1000,
                    value=0,
                )
            with col3:
                salary_max = st.number_input(
                    "Salary Max",
                    min_value=0,
                    step=1000,
                    value=0,
                )

            if st.form_submit_button("Save Job"):
                try:
                    job_service.create_job(
                        title=title,
                        company=company,
                        source=source,
                        source_url=source_url or None,
                        location=location or None,
                        work_mode=work_mode or None,
                        description=description or None,
                        required_skills=required_skills or None,
                        minimum_experience=int(minimum_experience),
                        salary_min=int(salary_min) if salary_min else None,
                        salary_max=int(salary_max) if salary_max else None,
                    )
                    st.success("Job saved.")
                except (ValueError, SQLAlchemyError) as exc:
                    st.error(f"Error saving job: {exc}")

    st.subheader("Discover and Filter Jobs")
    col1, col2, col3 = st.columns(3)
    with col1:
        title_or_company = st.text_input("Title or Company")
        location_filter = st.text_input(
            "Location",
            value=(candidate.preferred_locations or "").split(",")[0].strip()
            if candidate and candidate.preferred_locations
            else "",
        )
    with col2:
        work_mode_filter = st.selectbox(
            "Work Mode",
            options=["", "Remote", "Hybrid", "On-site"],
            index=0,
        )
        skills_filter = st.text_input(
            "Skills",
            value=candidate.skills if candidate else "",
        )
    with col3:
        experience_limit = st.number_input(
            "Maximum Candidate Experience",
            min_value=0,
            step=1,
            value=int(candidate.years_of_experience or 0)
            if candidate
            else 0,
        )

    experience_filter = (
        int(experience_limit) if experience_limit and experience_limit > 0 else None
    )
    jobs = job_service.filter_jobs(
        title_or_company=title_or_company,
        location=location_filter,
        work_mode=work_mode_filter,
        required_skills=skills_filter,
        maximum_experience=experience_filter,
    )

    if not jobs:
        st.info("No jobs match the current filters.")
        return

    ranked_matches = (
        matching_service.rank_jobs(candidate, jobs)
        if candidate
        else []
    )
    jobs_by_id = {job.id: job for job in jobs}

    if not candidate:
        for job in jobs:
            with st.container(border=True):
                st.markdown(f"### {job.title}")
                st.write(f"**Company:** {job.company}")
                st.write(f"**Location:** {job.location or 'Not specified'}")
                st.write(f"**Work Mode:** {job.work_mode or 'Not specified'}")
                st.write(f"**Source:** {job.source}")
                compensation = _format_compensation(job)
                if compensation:
                    st.write(f"**Compensation:** {compensation}")
                if job.required_skills:
                    st.write(f"**Required Skills:** {job.required_skills}")
                _show_source_links(job)
                if job.description:
                    with st.expander("Job Description"):
                        st.write(job.description)
        return

    for match in ranked_matches:
        job = jobs_by_id[match.job_id]
        with st.container(border=True):
            st.markdown(f"### {job.title}")
            st.progress(match.total_score)
            st.write(f"**Compatibility:** {match.total_score}/100")
            st.write(f"**Company:** {job.company}")
            st.write(f"**Location:** {job.location or 'Not specified'}")
            st.write(f"**Work Mode:** {job.work_mode or 'Not specified'}")
            st.write(f"**Source:** {job.source}")
            compensation = _format_compensation(job)
            if compensation:
                st.write(f"**Compensation:** {compensation}")
            if job.required_skills:
                st.write(f"**Required Skills:** {job.required_skills}")
            if match.matched_skills:
                st.write(
                    "**Matched Skills:** "
                    + ", ".join(match.matched_skills)
                )
            if match.missing_skills:
                st.write(
                    "**Missing Skills:** "
                    + ", ".join(match.missing_skills)
                )
            with st.expander("Why this score"):
                for reason in match.explanation:
                    st.write(f"- {reason}")
            if job.minimum_experience is not None:
                st.write(
                    f"**Minimum Experience:** {job.minimum_experience} years"
                )
            _show_source_links(job)
            if job.description:
                with st.expander("Job Description"):
                    st.write(job.description)


def _format_compensation(job):
    if job.salary_min is None and job.salary_max is None:
        return job.salary_text or None
    currency = job.salary_currency or "Unspecified currency"
    period = job.salary_period or "period unspecified"
    if currency == "INR" and period == "annual":
        minimum = job.salary_min / 100_000 if job.salary_min is not None else None
        maximum = job.salary_max / 100_000 if job.salary_max is not None else None
        suffix = "LPA"
        values = (
            f"{minimum:g}" if minimum is not None else "not specified",
            f"{maximum:g}" if maximum is not None else "not specified",
        )
    else:
        values = (
            f"{job.salary_min:,}" if job.salary_min is not None else "not specified",
            f"{job.salary_max:,}" if job.salary_max is not None else "not specified",
        )
        suffix = f"{currency} / {period}"
    if values[0] == values[1]:
        return f"{values[0]} {suffix}"
    return f"{values[0]} - {values[1]} {suffix}"


def _show_source_links(job):
    listings = job_service.get_job_source_listings(job.id)
    if not listings:
        if job.source_url:
            st.link_button("Open Job", job.source_url)
        return
    seen_urls = set()
    for index, listing in enumerate(listings):
        if not listing.source_url or listing.source_url in seen_urls:
            continue
        seen_urls.add(listing.source_url)
        st.link_button(
            f"Open on {listing.source_name}",
            listing.source_url,
            key=f"job-source-{job.id}-{index}",
        )
    if job.source_url and job.source_url not in seen_urls:
        st.link_button(
            "Open Job",
            job.source_url,
            key=f"job-source-{job.id}-canonical",
        )


if __name__ == "__main__":
    show_jobs_page()
