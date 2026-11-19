"""Review-only AI resume tailoring page."""
from sqlalchemy.exc import SQLAlchemyError
import streamlit as st

from app.services.candidate_service import candidate_service
from app.services.job_service import job_service
from app.services.resume_service import resume_service
from app.services.tailoring_service import tailoring_service


def show_tailoring_page():
    st.header("Resume Tailoring")

    candidates = candidate_service.get_all_candidates()
    if not candidates:
        st.warning("Create a candidate before generating a tailored resume.")
        return

    candidate_options = {
        f"{candidate.full_name} ({candidate.email})": candidate.id
        for candidate in candidates
    }
    selected_candidate = st.selectbox(
        "Candidate",
        options=list(candidate_options.keys()),
        key="tailoring_candidate",
    )
    candidate_id = candidate_options[selected_candidate]

    jobs = job_service.get_jobs()
    if not jobs:
        st.warning("Add a job before generating a tailored resume.")
        return

    job_options = {
        f"{job.title} at {job.company}": job.id
        for job in jobs
    }
    selected_job = st.selectbox(
        "Target Job",
        options=list(job_options.keys()),
        key="tailoring_job",
    )
    job_id = job_options[selected_job]

    resumes = resume_service.get_resumes_by_candidate(candidate_id)
    resume_options = {"No source resume": None}
    resume_options.update({
        f"{resume.file_name} ({resume.created_at.strftime('%Y-%m-%d')})": resume.id
        for resume in resumes
    })
    selected_resume = st.selectbox(
        "Source Resume",
        options=list(resume_options.keys()),
        key="tailoring_resume",
    )
    resume_id = resume_options[selected_resume]

    if st.button("Generate Draft"):
        with st.spinner("Generating a fact-grounded resume draft locally..."):
            try:
                generated = tailoring_service.generate_draft(
                    candidate_id=candidate_id,
                    job_id=job_id,
                    resume_id=resume_id,
                )
                draft_id = tailoring_service.save_draft(
                    candidate_id=candidate_id,
                    job_id=job_id,
                    resume_id=resume_id,
                    draft_text=generated["draft_text"],
                    suggestions=generated["suggestions"],
                    limitations=generated["limitations"],
                    prompt=generated["prompt"],
                    raw_response=generated["raw_response"],
                )
                st.success(
                    f"Draft {draft_id} generated. Review and approve it before export."
                )
            except (ValueError, SQLAlchemyError) as exc:
                st.error(f"Error generating draft: {exc}")

    drafts = tailoring_service.get_drafts(candidate_id, job_id)
    if not drafts:
        st.info("No tailored resume drafts exist for this candidate and job.")
        return

    draft_options = {
        f"Draft {draft.id} - "
        f"{'Approved' if draft.is_approved else 'Pending'}": draft.id
        for draft in drafts
    }
    selected_draft = st.selectbox(
        "Saved Draft",
        options=list(draft_options.keys()),
        key="tailoring_saved_draft",
    )
    draft_id = draft_options[selected_draft]
    draft = next(item for item in drafts if item.id == draft_id)

    with st.form(f"tailoring_review_{draft.id}"):
        draft_text = st.text_area(
            "Resume Draft",
            value=draft.draft_text,
            height=320,
        )
        suggestions = st.text_area(
            "Suggestions",
            value=draft.suggestions or "",
            height=140,
        )
        limitations = st.text_area(
            "Limitations",
            value=draft.limitations or "",
            height=120,
        )
        is_approved = st.checkbox(
            "Approve this tailored resume",
            value=draft.is_approved,
        )
        if st.form_submit_button("Save Review"):
            try:
                tailoring_service.review_draft(
                    draft_id=draft.id,
                    candidate_id=candidate_id,
                    draft_text=draft_text,
                    suggestions=suggestions,
                    limitations=limitations,
                    is_approved=is_approved,
                )
                st.success("Tailored resume review saved.")
            except (ValueError, SQLAlchemyError) as exc:
                st.error(f"Error saving tailored resume: {exc}")

    if draft.is_approved:
        st.download_button(
            "Download Approved Draft",
            data=draft.draft_text,
            file_name=f"tailored_resume_{draft.id}.txt",
            mime="text/plain",
        )
        if st.button("Save Export on Disk"):
            try:
                path = tailoring_service.export_draft(draft.id, candidate_id)
                st.success(f"Approved draft saved locally: {path}")
            except (ValueError, SQLAlchemyError) as exc:
                st.error(f"Error exporting draft: {exc}")


if __name__ == "__main__":
    show_tailoring_page()
