"""Manual job discovery, storage, filtering, and duplicate prevention page."""
from sqlalchemy.exc import SQLAlchemyError
import streamlit as st

from app.services.candidate_service import candidate_service
from app.services.job_service import job_service


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

    for job in jobs:
        with st.container(border=True):
            st.markdown(f"### {job.title}")
            st.write(f"**Company:** {job.company}")
            st.write(f"**Location:** {job.location or 'Not specified'}")
            st.write(f"**Work Mode:** {job.work_mode or 'Not specified'}")
            st.write(f"**Source:** {job.source}")
            if job.required_skills:
                st.write(f"**Required Skills:** {job.required_skills}")
            if job.minimum_experience is not None:
                st.write(
                    f"**Minimum Experience:** {job.minimum_experience} years"
                )
            if job.source_url:
                st.link_button("Open Job", job.source_url)
            if job.description:
                with st.expander("Job Description"):
                    st.write(job.description)


if __name__ == "__main__":
    show_jobs_page()
