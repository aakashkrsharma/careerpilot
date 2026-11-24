"""
CareerPilot - AI-powered candidate profile management system
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import streamlit as st

PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.database.database import init_db
from app.ui.dashboard_page import show_dashboard_page
from app.ui.profile_page import show_profile_page
from app.ui.jobs_page import show_jobs_page
from app.ui.job_discovery_page import show_job_discovery_page
from app.ui.tailoring_page import show_tailoring_page
from app.ui.batch_review_page import show_batch_review_page
from app.ui.clarification_queue_page import show_clarification_queue_page
from app.ui.application_tracker_page import show_application_tracker_page

NAVIGATION_OPTIONS = (
    "Dashboard",
    "Candidate Profile",
    "Jobs & Discovery",
    "Apply Workflow",
    "Application Tracker",
)


def _navigate_to(section: str) -> None:
    st.session_state["main_navigation"] = section


# Initialize database
init_db()

# Set up Streamlit page configuration
st.set_page_config(
    page_title="CareerPilot",
    page_icon="📊",
    layout="wide"
)

st.title("CareerPilot")
st.caption("Your local-first AI job-hunting assistant")
page = st.radio(
    "Main navigation",
    NAVIGATION_OPTIONS,
    horizontal=True,
    key="main_navigation",
    label_visibility="collapsed",
)

if page == "Dashboard":
    st.subheader("Quick actions")
    quick_actions = st.columns(4)
    quick_action_destinations = (
        "Candidate Profile",
        "Jobs & Discovery",
        "Apply Workflow",
        "Application Tracker",
    )
    for column, destination in zip(quick_actions, quick_action_destinations):
        column.button(
            destination,
            key=f"dashboard_quick_action_{destination}",
            on_click=_navigate_to,
            args=(destination,),
            use_container_width=True,
        )
    show_dashboard_page()
elif page == "Candidate Profile":
    show_profile_page()
elif page == "Jobs & Discovery":
    jobs_tab, discovery_tab = st.tabs(
        ("Ranked Matches & Manual Entry", "Source Management & Discovery")
    )
    with discovery_tab:
        show_job_discovery_page()
    with jobs_tab:
        show_jobs_page()
elif page == "Apply Workflow":
    batch_tab, tailoring_tab, clarification_tab = st.tabs(
        ("Batch Review", "Resume Tailoring", "Clarification Queue")
    )
    with batch_tab:
        show_batch_review_page()
    with tailoring_tab:
        show_tailoring_page()
    with clarification_tab:
        show_clarification_queue_page()
elif page == "Application Tracker":
    show_application_tracker_page()