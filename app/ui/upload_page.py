"""
Upload page for CareerPilot - handles resume uploads and initial processing
"""
import streamlit as st
from app.services.candidate_service import candidate_service
from app.services.extraction_service import extraction_service
from app.services.llm_service import llm_service
from app.services.resume_service import resume_service
from sqlalchemy.exc import SQLAlchemyError

def show_upload_page():
    """Display the upload page for resumes"""
    st.header("Upload Resume")
    
    # Create or select candidate
    st.subheader("Candidate Information")
    
    # Get existing candidates
    candidates = candidate_service.get_all_candidates()
    candidate_id = None
    
    if candidates:
        candidate_options = {f"{c.full_name} ({c.email})": c.id for c in candidates}
        selected_candidate = st.selectbox(
            "Select existing candidate", 
            options=list(candidate_options.keys()),
            key="existing_candidate"
        )
        candidate_id = candidate_options[selected_candidate]
    else:
        with st.form("new_candidate_form"):
            full_name = st.text_input("Full Name")
            email = st.text_input("Email")
            
            if st.form_submit_button("Create New Candidate"):
                if full_name and email:
                    candidate = candidate_service.create_candidate(
                        full_name=full_name,
                        email=email
                    )
                    candidate_id = candidate.id
                    st.success(f"Created new candidate: {candidate.full_name}")
                else:
                    st.error("Please fill in all fields")
    
    # Resume upload section
    st.subheader("Upload Resume")
    
    uploaded_file = st.file_uploader(
        "Choose a resume file (PDF, DOCX, or TXT)", 
        type=["pdf", "docx", "txt"],
        key="resume_uploader"
    )
    
    if uploaded_file is not None:
        # Display file info
        file_details = {
            "Filename": uploaded_file.name,
            "File size": f"{uploaded_file.size} bytes",
            "File type": uploaded_file.type
        }
        
        st.write("File details:")
        for key, value in file_details.items():
            st.write(f"- {key}: {value}")
        
        # Process the resume
        if st.button("Process Resume"):
            if candidate_id is None:
                st.error("Create or select a candidate before processing a resume.")
                return

            with st.spinner("Processing resume..."):
                try:
                    # Save the uploaded file
                    file_path = resume_service.save_resume_file(
                        file_name=uploaded_file.name,
                        file_content=uploaded_file.read()
                    )
                    
                    # Extract text from the file
                    extracted_text = resume_service.extract_text_from_file(file_path)
                    
                    # Create resume record in database
                    resume = resume_service.create_resume_record(
                        candidate_id=candidate_id,
                        file_name=uploaded_file.name,
                        file_path=file_path,
                        extracted_text=extracted_text
                    )
                    
                    # Extract information using LLM
                    extraction_result = llm_service.extract_information_from_resume(
                        resume_text=extracted_text,
                        candidate_id=candidate_id,
                        resume_id=resume.id
                    )
                    extraction_service.save_pending_extraction(extraction_result)
                    
                    st.success("Resume processed. Review the extracted information before approval.")
                    st.json(extraction_result["extracted_data"])
                except (ValueError, OSError, SQLAlchemyError) as e:
                    st.error(f"Error processing resume: {str(e)}")
    else:
        st.info("Please upload a resume file to get started")

# Initialize the page when imported
if __name__ == "__main__":
    show_upload_page()