"""
Dashboard page for CareerPilot - displays candidate profiles and resume information
"""
import streamlit as st
from app.services.candidate_service import candidate_service
from app.services.resume_service import resume_service
from app.database.models import Candidate, Resume, ExtractedInfo

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
        resumes = resume_service.get_candidate_resumes(candidate.id)
        extracted_infos = resume_service.get_candidate_extracted_info(candidate.id)
        
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
    st.dataframe(df, use_container_width=True)
    
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
        resumes = resume_service.get_candidate_resumes(candidate_id)
        extracted_infos = resume_service.get_candidate_extracted_info(candidate_id)
        
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

# Initialize the page when imported
if __name__ == "__main__":
    show_dashboard_page()