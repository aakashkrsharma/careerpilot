"""
Dashboard page for CareerPilot - displays candidate profiles and resume information
"""
import streamlit as st
from app.services.candidate_service import candidate_service
from app.services.resume_service import resume_service
from app.database.models import Candidate, Resume, ExtractedInfo
from app.services.application_service import application_service
from app.services.clarification_queue_service import clarification_queue_service

def show_dashboard_page():
    """Display the dashboard page with candidate information"""
    st.header("Dashboard")
    
    # Get all candidates
    candidates = candidate_service.get_all_candidates()
    
    if not candidates:
        st.info("No candidates found. Please upload a resume to get started.")
        return
    
    # Display candidates in a table
    st.subheader("Candidates")
    
    candidate_data = []
    for candidate in candidates:
        resumes = candidate_service.get_candidate_resumes(candidate.id)
        extracted_infos = candidate_service.get_candidate_extracted_info(candidate.id)
        
        candidate_data.append({
            "ID": candidate.id,
            "Name": candidate.full_name,
            "Email": candidate.email,
            "Resumes": len(resumes),
            "Extracted Info": len(extracted_infos),
            "Created": candidate.created_at.strftime('%Y-%m-%d')
        })
    
    # Convert to DataFrame for easier display
    import pandas as pd
    df = pd.DataFrame(candidate_data)
    st.dataframe(df, width="stretch")
    
    # Detailed view for selected candidate
    st.subheader("Candidate Details")
    
    candidate_options = {f"{c.full_name} ({c.email})": c.id for c in candidates}
    selected_candidate = st.selectbox(
        "Select candidate to view details", 
        options=list(candidate_options.keys()),
        key="dashboard_candidate"
    )
    
    if selected_candidate:
        candidate_id = candidate_options[selected_candidate]
        
        # Get detailed information
        candidate = candidate_service.get_candidate_by_id(candidate_id)
        resumes = candidate_service.get_candidate_resumes(candidate_id)
        extracted_infos = candidate_service.get_candidate_extracted_info(candidate_id)
        
        # Display candidate info
        st.markdown(f"### {candidate.full_name}")
        st.write(f"**Email:** {candidate.email}")
        st.write(f"**Phone:** {candidate.phone or 'Not provided'}")
        st.write(f"**Location:** {candidate.location or 'Not provided'}")
        st.write(f"**LinkedIn:** {candidate.linkedin or 'Not provided'}")
        st.write(f"**GitHub:** {candidate.github or 'Not provided'}")
        
        if candidate.summary:
            st.markdown("#### Summary")
            st.write(candidate.summary)
        if candidate.skills:
            st.write(f"**Skills:** {candidate.skills}")
        if candidate.experience:
            st.markdown("#### Experience")
            st.write(candidate.experience)
        if candidate.education:
            st.write(f"**Education:** {candidate.education}")
        if candidate.years_of_experience is not None:
            st.write(
                f"**Years of Experience:** {candidate.years_of_experience}"
            )
        if candidate.preferred_roles:
            st.write(f"**Preferred Roles:** {candidate.preferred_roles}")
        if candidate.preferred_locations:
            st.write(
                f"**Preferred Locations:** {candidate.preferred_locations}"
            )
        if candidate.work_modes:
            st.write(f"**Work Modes:** {candidate.work_modes}")
        if candidate.minimum_salary:
            st.write(f"**Minimum Salary:** {candidate.minimum_salary}")
        
        # Display resume information
        st.markdown("### Resumes")
        if resumes:
            for resume in resumes:
                st.markdown(f"**{resume.file_name}**")
                st.write(f"Uploaded: {resume.created_at.strftime('%Y-%m-%d %H:%M')}")
                st.write(f"Processed: {'Yes' if resume.is_processed else 'No'}")
                st.write("---")
        else:
            st.info("No resumes uploaded for this candidate.")
        
        # Display extracted information
        st.markdown("### Extracted Information")
        if extracted_infos:
            for info in extracted_infos:
                st.markdown(f"**From Resume: {info.resume_id}**")
                if info.is_approved:
                    st.success("Approved")
                else:
                    st.warning("Not approved")
                
                # Display key information
                if info.full_name:
                    st.write(f"**Name:** {info.full_name}")
                if info.email:
                    st.write(f"**Email:** {info.email}")
                if info.summary:
                    st.markdown("**Summary:**")
                    st.write(info.summary[:200] + "..." if len(info.summary) > 200 else info.summary)
                
                st.write("---")
        else:
            st.info("No extracted information for this candidate.")

        st.markdown("### Application Status")
        status_counts = application_service.get_status_counts(candidate_id)
        unresolved_count = len(clarification_queue_service.get_queue(candidate_id))
        total_applications = sum(status_counts.values())
        columns = st.columns(4)
        columns[0].metric("Applications", total_applications)
        columns[1].metric(
            "Needs Clarification",
            status_counts.get("needs_clarification", 0),
        )
        columns[2].metric("Ready", status_counts.get("ready", 0))
        columns[3].metric("Applied", status_counts.get("applied", 0))
        st.caption(
            f"Unresolved screening questions: {unresolved_count}. "
            "Application records are retained permanently."
        )

# Initialize the page when imported
if __name__ == "__main__":
    show_dashboard_page()