"""Track permanent application history and candidate-controlled completion."""
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from app.services.application_executor import ManualApplicationExecutor
from app.services.application_packet_service import application_packet_service
from app.services.application_service import application_service
from app.services.candidate_service import candidate_service
from app.services.job_service import job_service
from app.services.tailoring_service import tailoring_service


manual_executor = ManualApplicationExecutor()


def show_application_tracker_page():
    st.header("Application Tracker")
    st.caption(
        "Application history is retained permanently. CareerPilot does not "
        "submit applications through login or CAPTCHA walls."
    )
    candidates = candidate_service.get_all_candidates()
    if not candidates:
        st.info("Create a candidate before tracking applications.")
        return

    candidate_options = {
        f"{candidate.full_name} ({candidate.email})": candidate.id
        for candidate in candidates
    }
    selected_candidate = st.selectbox(
        "Candidate",
        options=list(candidate_options.keys()),
        key="application_tracker_candidate",
    )
    candidate_id = candidate_options[selected_candidate]
    applications = application_service.get_application_history(candidate_id)
    if not applications:
        st.info("No application records exist yet. Build a batch to get started.")
        return

    summary = [
        {
            "Application": application.id,
            "Job ID": application.job_id,
            "Status": application.status.replace("_", " ").title(),
            "Match": application.match_score,
            "Stage": application.match_stage,
            "Applied": (
                application.applied_at.strftime("%Y-%m-%d")
                if application.applied_at
                else ""
            ),
        }
        for application in applications
    ]
    st.dataframe(pd.DataFrame(summary), hide_index=True, width="stretch")
    if st.button("Export History to CSV", key="tracker_export_csv"):
        export_dir = Path("data/exports")
        export_dir.mkdir(parents=True, exist_ok=True)
        export_path = export_dir / f"applications_candidate_{candidate_id}.csv"
        pd.DataFrame(summary).to_csv(export_path, index=False)
        st.success(f"History exported: {export_path}")

    for application in applications:
        job = job_service.get_job_by_id(application.job_id)
        if job is None:
            continue
        with st.container(border=True):
            st.markdown(f"### Application {application.id}: {job.title}")
            st.write(
                f"**Company:** {job.company} | **Status:** "
                f"{application.status.replace('_', ' ').title()}"
            )
            st.write(
                f"**Source:** {job.source} | **Match:** "
                f"{application.match_score if application.match_score is not None else 'Not scored'}"
            )
            if application.source_url:
                st.link_button("Open Job", application.source_url)
            if st.button(
                "Prepare Application Packet",
                key=f"tracker_packet_{application.id}",
            ):
                try:
                    packet_dir = application_packet_service.prepare_packet(
                        candidate_id=candidate_id, application_id=application.id
                    )
                    st.success(f"Packet ready: {packet_dir}")
                except (ValueError, OSError) as exc:
                    st.error(f"Could not prepare packet: {exc}")
            if application.status == "discovered":
                drafts = [
                    draft
                    for draft in tailoring_service.get_drafts(
                        candidate_id,
                        job.id,
                    )
                    if draft.is_approved
                ]
                if drafts:
                    draft_options = {
                        f"Approved draft {draft.id}": draft.id
                        for draft in drafts
                    }
                    selected_draft = st.selectbox(
                        "Approved tailored resume",
                        options=list(draft_options.keys()),
                        key=f"tracker_resume_{application.id}",
                    )
                    if st.button(
                        "Attach Resume and Mark Tailored",
                        key=f"tracker_tailor_{application.id}",
                    ):
                        try:
                            application_service.transition_status(
                                application.id,
                                candidate_id,
                                "tailored",
                                actor="candidate",
                                reason="Candidate attached an approved tailored resume.",
                                require_tailored_approval=True,
                                tailored_resume_id=draft_options[selected_draft],
                            )
                            st.success("Approved resume linked to application.")
                            st.rerun()
                        except (ValueError, SQLAlchemyError) as exc:
                            st.error(f"Could not update application: {exc}")

            if application.status in {
                "discovered",
                "tailored",
                "needs_clarification",
            }:
                if st.button(
                    "Mark Ready for Application",
                    key=f"tracker_ready_{application.id}",
                ):
                    try:
                        application_service.transition_status(
                            application.id,
                            candidate_id,
                            "ready",
                            actor="candidate",
                            reason="Candidate approved the prepared application.",
                            require_tailored_approval=True,
                        )
                        st.success("Application is ready for manual handoff.")
                        st.rerun()
                    except (ValueError, SQLAlchemyError) as exc:
                        st.error(f"Could not mark application ready: {exc}")

            if application.status == "ready":
                if st.button(
                    "Prepare Manual Handoff",
                    key=f"tracker_handoff_{application.id}",
                ):
                    try:
                        result = manual_executor.execute(
                            application,
                            job,
                            candidate_approved=True,
                        )
                        application_service.prepare_manual_handoff(
                            application.id,
                            candidate_id,
                            candidate_approved=True,
                            instructions=result.manual_instructions or result.message,
                        )
                        st.success(result.message)
                        st.rerun()
                    except (ValueError, SQLAlchemyError) as exc:
                        st.error(f"Could not prepare handoff: {exc}")

            if application.status == "manual_required":
                st.info(application.manual_instructions or "Complete the application directly.")
                confirmed = st.checkbox(
                    "I completed and submitted this application on the source site",
                    key=f"tracker_confirm_{application.id}",
                )
                if st.button(
                    "Confirm Application Completed",
                    key=f"tracker_applied_{application.id}",
                    disabled=not confirmed,
                ):
                    try:
                        application_service.confirm_manual_application(
                            application.id,
                            candidate_id,
                            candidate_confirmed=confirmed,
                        )
                        st.success(
                            "Application marked Applied and retained in history."
                        )
                        st.rerun()
                    except (ValueError, SQLAlchemyError) as exc:
                        st.error(f"Could not confirm application: {exc}")

            if application.applied_at:
                st.write(
                    f"**Applied:** {application.applied_at.strftime('%Y-%m-%d %H:%M')}"
                )
            if application.follow_up_at:
                st.write(
                    f"**Follow up:** {application.follow_up_at.strftime('%Y-%m-%d')}"
                )
            if application.status == "applied":
                if st.button(
                    "Mark Follow-Up",
                    key=f"tracker_followup_{application.id}",
                ):
                    try:
                        application_service.transition_status(
                            application.id,
                            candidate_id,
                            "follow_up",
                            actor="candidate",
                            reason="Candidate scheduled a follow-up.",
                        )
                        st.success("Follow-up recorded.")
                        st.rerun()
                    except (ValueError, SQLAlchemyError) as exc:
                        st.error(f"Could not record follow-up: {exc}")


if __name__ == "__main__":
    show_application_tracker_page()
