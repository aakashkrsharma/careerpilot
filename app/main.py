"""
CareerPilot - AI-powered candidate profile management system
"""
import streamlit as st
from app.database.database import init_db
from app.services.candidate_service import CandidateService
from app.services.resume_service import ResumeService
from app.ui.upload_page import show_upload_page
from app.ui.review_page import show_review_page
from app.ui.dashboard_page import show_dashboard_page
from app.ui.profile_page import show_profile_page
from app.ui.jobs_page import show_jobs_page
from app.ui.job_discovery_page import show_job_discovery_page
from app.ui.tailoring_page import show_tailoring_page
from app.ui.batch_review_page import show_batch_review_page
from app.ui.clarification_queue_page import show_clarification_queue_page
from app.ui.application_tracker_page import show_application_tracker_page

# Initialize database
init_db()

# Set up Streamlit page configuration
st.set_page_config(
    page_title="CareerPilot",
    page_icon="📊",
    layout="wide"
)

# App title and description
st.title("📊 CareerPilot - AI-powered Candidate Profile Management")
st.markdown("""
Welcome to CareerPilot, your local-first AI job hunting assistant.
Upload your resume, let AI extract information, review it, and store your profile.
""")

# Navigation sidebar
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to",
    [
        "Dashboard",
        "Candidate Profile",
        "Jobs",
        "Discover Jobs",
        "Resume Tailoring",
        "Batch Review",
        "Clarification Queue",
        "Application Tracker",
        "Upload Resume",
        "Review Information",
    ],
)

# Page routing
if page == "Dashboard":
    show_dashboard_page()
elif page == "Candidate Profile":
    show_profile_page()
elif page == "Jobs":
    show_jobs_page()
elif page == "Discover Jobs":
    show_job_discovery_page()
elif page == "Resume Tailoring":
    show_tailoring_page()
elif page == "Batch Review":
    show_batch_review_page()
elif page == "Clarification Queue":
    show_clarification_queue_page()
elif page == "Application Tracker":
    show_application_tracker_page()
elif page == "Upload Resume":
    show_upload_page()
elif page == "Review Information":
    show_review_page()

# Initialize services
candidate_service = CandidateService()
resume_service = ResumeService()