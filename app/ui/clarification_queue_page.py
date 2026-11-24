"""Collect explicit candidate answers for unresolved screening questions."""
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from app.services.application_service import application_service
from app.services.candidate_service import candidate_service
from app.services.clarification_queue_service import clarification_queue_service


def show_clarification_queue_page():
    st.header("Clarification Queue")
    candidates = candidate_service.get_all_candidates()
    if not candidates:
        st.info("Create a candidate before adding screening questions.")
        return

    candidate_options = {
        f"{candidate.full_name} ({candidate.email})": candidate.id
        for candidate in candidates
    }
    selected_candidate = st.selectbox(
        "Candidate",
        options=list(candidate_options.keys()),
        key="clarification_candidate",
    )
    candidate_id = candidate_options[selected_candidate]
    applications = application_service.get_application_history(candidate_id)

    st.subheader("Add a Screening Question")
    if not applications:
        st.info("Create or approve a batch before assessing application questions.")
    else:
        application_options = {}
        for application in applications:
            label = (
                f"Application {application.id} - Job {application.job_id} "
                f"({application.status})"
            )
            application_options[label] = application.id
        with st.form("add_screening_question"):
            selected_application = st.selectbox(
                "Application",
                options=list(application_options.keys()),
            )
            question_text = st.text_area("Question text")
            canonical_key = st.text_input(
                "Canonical answer key (optional)",
                help="Use a stable key such as expected_ctc or notice_period.",
            )
            proposed_answer = st.text_input("Proposed answer (optional)")
            category = st.text_input("Question category (optional)")
            sensitivity = st.selectbox(
                "Sensitivity",
                options=["normal", "sensitive", "high_stakes"],
            )
            ambiguous = st.checkbox("The question or answer is ambiguous")
            required = st.checkbox("This question is required", value=True)
            assess = st.form_submit_button("Assess Question")

        if assess:
            try:
                result = clarification_queue_service.assess_questions(
                    application_options[selected_application],
                    candidate_id,
                    [{
                        "question_text": question_text,
                        "canonical_key": canonical_key or None,
                        "proposed_answer": proposed_answer or None,
                        "category": category or None,
                        "sensitivity": sensitivity,
                        "ambiguous": ambiguous,
                        "required": required,
                    }],
                )
                if result.auto_answers:
                    st.success(
                        "An approved answer was reused: "
                        + "; ".join(
                            f"{key}: {value}"
                            for key, value in result.auto_answers.items()
                        )
                    )
                if result.request_ids:
                    st.warning(
                        f"Candidate input is required for request(s): "
                        f"{', '.join(map(str, result.request_ids))}."
                    )
                elif not result.auto_answers:
                    st.info("No clarification was needed for this optional question.")
            except (ValueError, SQLAlchemyError) as exc:
                st.error(f"Could not assess question: {exc}")

    st.subheader("Bulk Question Import")
    if applications:
        with st.form("bulk_screening_questions"):
            bulk_application = st.selectbox(
                "Application for bulk questions",
                options=list(application_options.keys()),
                key="bulk_application",
            )
            bulk_text = st.text_area(
                "Paste screening questions (one per line)",
                height=150,
            )
            bulk_assess = st.form_submit_button("Assess Bulk Questions")
        if bulk_assess and bulk_text.strip():
            questions = [
                {
                    "question_text": line.strip(),
                    "canonical_key": None,
                    "proposed_answer": None,
                    "category": None,
                    "sensitivity": "normal",
                    "ambiguous": False,
                    "required": True,
                }
                for line in bulk_text.splitlines()
                if line.strip()
            ]
            try:
                result = clarification_queue_service.assess_questions(
                    application_options[bulk_application],
                    candidate_id,
                    questions,
                )
                st.success(
                    f"Assessed {len(questions)} question(s). "
                    f"Auto-answered: {len(result.auto_answers)}; "
                    f"queued: {len(result.request_ids)}."
                )
            except (ValueError, SQLAlchemyError) as exc:
                st.error(f"Could not assess bulk questions: {exc}")

    queue = clarification_queue_service.get_queue(candidate_id)
    st.subheader("Questions Requiring Your Input")
    if not queue:
        st.success("There are no unresolved clarification requests.")
        return

    for item in queue:
        request = item.request
        with st.container(border=True):
            st.markdown(
                f"### {item.job.title} at {item.job.company}"
            )
            st.write(f"**Question:** {request.question_text}")
            st.write(
                f"**Category:** {request.category or 'General'} | "
                f"**Sensitivity:** {request.sensitivity}"
            )
            if request.proposed_answer:
                st.info(f"Suggested answer for your review: {request.proposed_answer}")
            with st.form(f"resolve_clarification_{request.id}"):
                candidate_answer = st.text_area(
                    "Your answer",
                    key=f"clarification_answer_{request.id}",
                )
                save_to_bank = st.checkbox(
                    "Save this approved answer for future applications",
                    value=True,
                    key=f"clarification_save_{request.id}",
                )
                scope = st.selectbox(
                    "Answer scope",
                    options=["global", "company", "role", "source", "job"],
                    key=f"clarification_scope_{request.id}",
                    disabled=not save_to_bank,
                )
                scope_value = st.text_input(
                    "Scope value (not needed for global answers)",
                    key=f"clarification_scope_value_{request.id}",
                    disabled=not save_to_bank or scope == "global",
                )
                aliases = st.text_input(
                    "Question aliases (optional, comma-separated)",
                    key=f"clarification_aliases_{request.id}",
                    disabled=not save_to_bank,
                )
                approved = st.checkbox(
                    "I confirm this answer is accurate and approve it",
                    key=f"clarification_approved_{request.id}",
                )
                resolve = st.form_submit_button("Save Answer")

            if resolve:
                try:
                    clarification_queue_service.resolve_request(
                        request.id,
                        candidate_id,
                        candidate_answer=candidate_answer,
                        candidate_approved=approved,
                        save_to_answer_bank=save_to_bank,
                        scope=scope,
                        scope_value=scope_value or None,
                        aliases=aliases or None,
                    )
                    st.success("Answer saved and clarification resolved.")
                    st.rerun()
                except (ValueError, SQLAlchemyError) as exc:
                    st.error(f"Could not resolve clarification: {exc}")


if __name__ == "__main__":
    show_clarification_queue_page()
