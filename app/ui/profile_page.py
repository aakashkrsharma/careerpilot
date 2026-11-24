"""Candidate profile editing and resume onboarding."""
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from app.services.candidate_service import candidate_service
from app.services.resume_service import resume_service
from app.ui.review_page import show_inline_extraction_review
from app.ui.upload_page import process_uploaded_resume


WORK_MODES = ("Remote", "Hybrid", "On-site")
PENDING_REVIEW_KEY = "profile_pending_resume_review"
SELECTED_CANDIDATE_KEY = "profile_selected_candidate_id"


def _show_candidate_creation() -> None:
    st.info("Create a candidate profile to get started.")
    with st.form("create_initial_candidate"):
        full_name = st.text_input("Full Name")
        email = st.text_input("Email")
        submitted = st.form_submit_button("Create Candidate", type="primary")

    if not submitted:
        return
    if not full_name.strip() or not email.strip():
        st.error("Full name and email are required.")
        return
    try:
        candidate = candidate_service.create_candidate(
            full_name=full_name.strip(),
            email=email.strip(),
        )
        st.session_state[SELECTED_CANDIDATE_KEY] = candidate.id
        st.session_state["profile_candidate_selector"] = (
            f"{candidate.full_name} ({candidate.email})"
        )
        st.rerun()
    except (ValueError, SQLAlchemyError) as exc:
        st.error(f"Could not create candidate: {exc}")


def _show_profile_editor(candidate) -> None:
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

        if not st.form_submit_button("Save Profile"):
            return
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


def show_profile_page():
    """Display candidate selection, resume onboarding, and profile editing."""
    st.header("Candidate Profile")
    if st.session_state.pop("profile_confirmation_notice", False):
        st.success("Details confirmed and saved to the candidate profile.")

    candidates = candidate_service.get_all_candidates()
    if not candidates:
        _show_candidate_creation()
        return
    pending_label = st.session_state.pop("profile_candidate_label_pending", None)
    if pending_label:
        st.session_state["profile_candidate_selector"] = pending_label

    candidate_options = {
        f"{candidate.full_name} ({candidate.email})": candidate.id
        for candidate in candidates
    }
    labels = list(candidate_options)
    pending = st.session_state.get(PENDING_REVIEW_KEY)
    selected_id = (
        pending["candidate_id"]
        if pending
        else st.session_state.get(SELECTED_CANDIDATE_KEY)
    )
    selected_label = next(
        (
            label
            for label, candidate_id in candidate_options.items()
            if candidate_id == selected_id
        ),
        labels[0],
    )

    selector_column, upload_column = st.columns([2, 1])
    with selector_column:
        selected_label = st.selectbox(
            "Select candidate",
            options=labels,
            index=labels.index(selected_label),
            key="profile_candidate_selector",
            disabled=pending is not None,
        )
    candidate_id = candidate_options[selected_label]
    st.session_state[SELECTED_CANDIDATE_KEY] = candidate_id
    candidate = candidate_service.get_candidate_by_id(candidate_id)
    if candidate is None:
        st.error("The selected candidate could not be found.")
        return

    with upload_column:
        st.subheader("Upload Resume")
        upload_key = (
            "profile_resume_uploader_"
            f"{st.session_state.get('profile_upload_version', 0)}"
        )
        uploaded_file = st.file_uploader(
            "PDF, DOCX, or TXT",
            type=["pdf", "docx", "txt"],
            key=upload_key,
            disabled=pending is not None,
            label_visibility="collapsed",
        )
        process_clicked = st.button(
            "Process Resume",
            key="profile_process_resume",
            type="primary",
            disabled=uploaded_file is None or pending is not None,
            use_container_width=True,
        )

    if pending is None and process_clicked and uploaded_file is not None:
        try:
            pending = process_uploaded_resume(candidate_id, uploaded_file)
            st.session_state[PENDING_REVIEW_KEY] = pending
            st.rerun()
        except (ValueError, OSError, SQLAlchemyError) as exc:
            st.error(f"Error processing resume: {exc}")

    resumes = resume_service.get_resumes_by_candidate(candidate_id)
    if pending is not None:
        st.divider()
        confirmed = show_inline_extraction_review(
            pending["candidate_id"],
            pending["resume_id"],
        )
        if confirmed:
            reviewed_candidate = candidate_service.get_candidate_by_id(
                pending["candidate_id"]
            )
            st.session_state[SELECTED_CANDIDATE_KEY] = pending["candidate_id"]
            st.session_state["profile_confirmation_notice"] = True
            if reviewed_candidate:
                st.session_state["profile_candidate_label_pending"] = (
                    f"{reviewed_candidate.full_name} ({reviewed_candidate.email})"
                )
            st.session_state.pop(PENDING_REVIEW_KEY, None)
            st.session_state["profile_upload_version"] = (
                st.session_state.get("profile_upload_version", 0) + 1
            )
            st.rerun()
        return

    st.divider()
    _show_profile_editor(candidate)

    st.subheader("Resumes")
    if resumes:
        for resume in resumes:
            status = "Processed" if resume.is_processed else "Processing incomplete"
            st.write(f"**{resume.file_name}** · {status}")
    else:
        st.info("No resumes uploaded for this candidate.")


if __name__ == "__main__":
    show_profile_page()
