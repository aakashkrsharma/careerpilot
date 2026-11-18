"""
Review page for CareerPilot - allows users to review and approve LLM-extracted information
"""
import streamlit as st
from app.services.candidate_service import candidate_service
from app.services.resume_service import resume_service
from app.database.models import Candidate, Resume, ExtractedInfo
from app.database.database import get_db

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
    db = next(get_db())
    try:
        extracted_info = db.query(ExtractedInfo).filter(
            ExtractedInfo.resume_id == resume_id
        ).first()
    finally:
        db.close()
    
    if not extracted_info:
        st.warning("No extracted information found for this resume.")
        return
    
    # Display extracted information
    st.subheader("Extracted Information")
    
    # Create editable fields for each extracted field
    with st.form("review_form"):
        updated_info = {}
        
        # Display and allow editing of each field
        updated_info["full_name"] = st.text_input(
            "Full Name", 
            value=extracted_info.full_name or ""
        )
        updated_info["email"] = st.text_input(
            "Email", 
            value=extracted_info.email or ""
        )
        updated_info["phone"] = st.text_input(
            "Phone", 
            value=extracted_info.phone or ""
        )
        updated_info["location"] = st.text_input(
            "Location", 
            value=extracted_info.location or ""
        )
        updated_info["linkedin"] = st.text_input(
            "LinkedIn", 
            value=extracted_info.linkedin or ""
        )
        updated_info["github"] = st.text_input(
            "GitHub", 
            value=extracted_info.github or ""
        )
        
        # Summary
        updated_info["summary"] = st.text_area(
            "Summary", 
            value=extracted_info.summary or "",
            height=150
        )
        
        # Experience
        updated_info["experience"] = st.text_area(
            "Experience", 
            value=extracted_info.experience or "",
            height=200
        )
        
        # Skills
        updated_info["skills"] = st.text_area(
            "Skills", 
            value=extracted_info.skills or "",
            height=150
        )
        
        # Education
        updated_info["education"] = st.text_area(
            "Education", 
            value=extracted_info.education or "",
            height=200
        )
        
        # Approval status
        is_approved = st.checkbox(
            "Approve this information",
            value=extracted_info.is_approved
        )
        
        # Submit button
        if st.form_submit_button("Update and Save"):
            try:
                # Update the extracted info in database
                db = next(get_db())
                try:
                    # Update the extracted info record
                    for key, value in updated_info.items():
                        setattr(extracted_info, key, value)
                    
                    extracted_info.is_approved = is_approved
                    
                    db.commit()
                    db.refresh(extracted_info)
                    
                    st.success("Extracted information updated successfully!")
                    
                except Exception as e:
                    db.rollback()
                    st.error(f"Error updating information: {str(e)}")
                finally:
                    db.close()
                    
            except Exception as e:
                st.error(f"Error saving information: {str(e)}")

# Initialize the page when imported
if __name__ == "__main__":
    show_review_page()