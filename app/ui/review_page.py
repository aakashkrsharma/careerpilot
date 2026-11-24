"""
Review page for CareerPilot - allows users to review and approve LLM-extracted information
"""
import streamlit as st
from app.services.candidate_service import candidate_service
from app.services.extraction_service import extraction_service
from app.services.resume_service import resume_service
from sqlalchemy.exc import SQLAlchemyError


def show_inline_extraction_review(candidate_id: int, resume_id: int) -> bool:
    """Render an in-page review and confirm the candidate's extracted details."""
    extracted_info = extraction_service.get_extraction_for_resume(
        candidate_id,
        resume_id,
    )
    if extracted_info is None:
        st.error("The processed resume has no saved extraction to review.")
        return False

    st.subheader("Review & Confirm Details")
    st.caption(
        "Check the extracted information carefully. Existing profile values "
        "are preserved unless you explicitly choose to replace them."
    )
    with st.form(f"profile_inline_review_{extracted_info['id']}"):
        updated_info = {}
        text_fields = {
            "full_name": "Full Name",
            "email": "Email",
            "phone": "Phone",
            "location": "Location",
            "linkedin": "LinkedIn",
            "github": "GitHub",
        }
        for field, label in text_fields.items():
            updated_info[field] = st.text_input(
                label,
                value=extracted_info[field] or "",
                key=f"profile_review_{extracted_info['id']}_{field}",
            )
        for field, label, height in (
            ("summary", "Summary", 150),
            ("experience", "Experience", 200),
            ("skills", "Skills", 150),
            ("education", "Education", 200),
        ):
            updated_info[field] = st.text_area(
                label,
                value=extracted_info[field] or "",
                height=height,
                key=f"profile_review_{extracted_info['id']}_{field}",
            )
        replace_existing = st.checkbox(
            "Replace existing profile values with the confirmed resume details",
            value=False,
            key=f"profile_review_{extracted_info['id']}_replace",
        )
        confirmed = st.form_submit_button("Confirm & Save", type="primary")

    if not confirmed:
        return False
    try:
        extraction_service.save_review(
            extraction_id=extracted_info["id"],
            candidate_id=candidate_id,
            updated_fields=updated_info,
            is_approved=True,
            replace_existing=replace_existing,
        )
        return True
    except (ValueError, SQLAlchemyError) as exc:
        st.error(f"Could not save confirmed details: {exc}")
        return False


def show_review_page():
    """Display the review page for extracted information"""
    st.header("Review Extracted Information")
    
    # Get all candidates
    candidates = candidate_service.get_all_candidates()
    
    if not candidates:
        st.warning("No candidates found. Please upload a resume first.")
        return
    
    # Select candidate
    candidate_options = {f"{c.full_name} ({c.email})": c.id for c in candidates}
    selected_candidate = st.selectbox(
        "Select candidate to review", 
        options=list(candidate_options.keys()),
        key="review_candidate"
    )
    
    candidate_id = candidate_options[selected_candidate]
    
    # Get candidate's resumes
    resumes = resume_service.get_resumes_by_candidate(candidate_id)
    
    if not resumes:
        st.warning("No resumes found for this candidate.")
        return
    
    # Select resume
    resume_options = {f"{r.file_name} ({r.created_at.strftime('%Y-%m-%d')})": r.id for r in resumes}
    selected_resume = st.selectbox(
        "Select resume to review", 
        options=list(resume_options.keys()),
        key="review_resume"
    )
    
    resume_id = resume_options[selected_resume]
    
    # Get extracted information for this resume
    extracted_info = extraction_service.get_extraction_for_resume(
        candidate_id,
        resume_id,
    )
    
    if not extracted_info:
        st.warning("No extracted information found for this resume.")
        return
    
    # Display extracted information
    st.subheader("Extracted Information")
    
    # Create editable fields for each extracted field
    with st.form(f"review_form_{extracted_info['id']}"):
        updated_info = {}
        
        text_fields = {
            "full_name": "Full Name",
            "email": "Email",
            "phone": "Phone",
            "location": "Location",
            "linkedin": "LinkedIn",
            "github": "GitHub",
        }
        for field, label in text_fields.items():
            updated_info[field] = st.text_input(
                label,
                value=extracted_info[field] or "",
                key=f"review_{extracted_info['id']}_{field}",
            )

        updated_info["summary"] = st.text_area(
            "Summary",
            value=extracted_info["summary"] or "",
            height=150,
            key=f"review_{extracted_info['id']}_summary",
        )
        updated_info["experience"] = st.text_area(
            "Experience",
            value=extracted_info["experience"] or "",
            height=200,
            key=f"review_{extracted_info['id']}_experience",
        )
        updated_info["skills"] = st.text_area(
            "Skills",
            value=extracted_info["skills"] or "",
            height=150,
            key=f"review_{extracted_info['id']}_skills",
        )
        updated_info["education"] = st.text_area(
            "Education",
            value=extracted_info["education"] or "",
            height=200,
            key=f"review_{extracted_info['id']}_education",
        )

        is_approved = st.checkbox(
            "Approve this information",
            value=extracted_info["is_approved"],
            key=f"review_{extracted_info['id']}_approved",
        )
        replace_existing = st.checkbox(
            "Replace existing candidate profile values with approved values",
            value=False,
            key=f"review_{extracted_info['id']}_replace",
        )

        if st.form_submit_button("Update and Save"):
            try:
                extraction_service.save_review(
                    extraction_id=extracted_info["id"],
                    candidate_id=candidate_id,
                    updated_fields=updated_info,
                    is_approved=is_approved,
                    replace_existing=replace_existing,
                )
                st.success("Reviewed information saved.")
            except (ValueError, SQLAlchemyError) as e:
                st.error(f"Error saving information: {str(e)}")

# Initialize the page when imported
if __name__ == "__main__":
    show_review_page()