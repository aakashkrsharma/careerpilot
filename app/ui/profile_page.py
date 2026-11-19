"""Editable candidate profile and job-search preference page."""
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from app.services.candidate_service import candidate_service


WORK_MODES = ("Remote", "Hybrid", "On-site")


def show_profile_page():
    st.header("Candidate Profile")

    candidates = candidate_service.get_all_candidates()
    if not candidates:
        st.warning("Create a candidate from Upload Resume before editing a profile.")
        return

    candidate_options = {
        f"{candidate.full_name} ({candidate.email})": candidate.id
        for candidate in candidates
    }
    selected_candidate = st.selectbox(
        "Select candidate",
        options=list(candidate_options.keys()),
        key="profile_candidate",
    )
    candidate_id = candidate_options[selected_candidate]
    candidate = candidate_service.get_candidate_by_id(candidate_id)
    if candidate is None:
        st.error("The selected candidate could not be found.")
        return

    with st.form(f"profile_form_{candidate.id}"):
        st.subheader("Profile")
        full_name = st.text_input("Full Name", value=candidate.full_name or "")
        email = st.text_input("Email", value=candidate.email or "")
        phone = st.text_input("Phone", value=candidate.phone or "")
        location = st.text_input("Location", value=candidate.location or "")
        linkedin = st.text_input("LinkedIn", value=candidate.linkedin or "")
        github = st.text_input("GitHub", value=candidate.github or "")
        summary = st.text_area("Professional Summary", value=candidate.summary or "")
        experience = st.text_area("Experience", value=candidate.experience or "")
        skills = st.text_area(
            "Skills",
            value=candidate.skills or "",
            help="Enter comma-separated skills.",
        )
        education = st.text_area("Education", value=candidate.education or "")
        years_of_experience = st.number_input(
            "Years of Experience",
            min_value=0,
            step=1,
            value=int(candidate.years_of_experience or 0),
        )

        st.subheader("Job Preferences")
        preferred_roles = st.text_input(
            "Preferred Roles",
            value=candidate.preferred_roles or "",
            help="Enter comma-separated job titles.",
        )
        preferred_locations = st.text_input(
            "Preferred Locations",
            value=candidate.preferred_locations or "",
            help="Enter comma-separated locations.",
        )
        selected_modes = [
            mode
            for mode in (candidate.work_modes or "").split(",")
            if mode.strip()
        ]
        work_modes = st.multiselect(
            "Work Modes",
            options=list(WORK_MODES),
            default=[mode for mode in selected_modes if mode in WORK_MODES],
        )
        minimum_salary = st.number_input(
            "Minimum Salary",
            min_value=0,
            step=1000,
            value=int(candidate.minimum_salary or 0),
        )

        if st.form_submit_button("Save Profile"):
            if not full_name.strip() or not email.strip():
                st.error("Full name and email are required.")
                return
            try:
                candidate_service.update_candidate(
                    candidate_id=candidate.id,
                    full_name=full_name.strip(),
                    email=email.strip(),
                    phone=phone.strip() or None,
                    location=location.strip() or None,
                    linkedin=linkedin.strip() or None,
                    github=github.strip() or None,
                    summary=summary.strip() or None,
                    experience=experience.strip() or None,
                    skills=skills.strip() or None,
                    education=education.strip() or None,
                    years_of_experience=int(years_of_experience),
                    preferred_roles=preferred_roles.strip() or None,
                    preferred_locations=preferred_locations.strip() or None,
                    work_modes=", ".join(work_modes) or None,
                    minimum_salary=int(minimum_salary),
                )
                st.success("Candidate profile saved.")
            except (ValueError, SQLAlchemyError) as exc:
                st.error(f"Error saving profile: {exc}")


if __name__ == "__main__":
    show_profile_page()
