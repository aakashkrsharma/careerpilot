"""Review and explicitly approve progressive application batches."""
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from app.services.application_packet_service import application_packet_service
from app.services.application_preparation_service import application_preparation_service
from app.services.batch_selection_service import batch_selection_service
from app.services.candidate_service import candidate_service


def show_batch_review_page():
    st.header("Batch Review")
    candidates = candidate_service.get_all_candidates()
    if not candidates:
        st.info("Create a candidate and add jobs before building an application batch.")
        return

    candidate_options = {
        f"{candidate.full_name} ({candidate.email})": candidate.id
        for candidate in candidates
    }
    selected_candidate = st.selectbox(
        "Candidate",
        options=list(candidate_options.keys()),
        key="batch_review_candidate",
    )
    candidate_id = candidate_options[selected_candidate]

    with st.form("build_application_batch"):
        requested_count = st.number_input(
            "Maximum jobs in this batch",
            min_value=1,
            max_value=20,
            value=20,
            step=1,
        )
        matching_threshold = st.slider(
            "Strict matching score threshold",
            min_value=0,
            max_value=100,
            value=70,
        )
        fallback_score = st.slider(
            "Minimum fallback score",
            min_value=0,
            max_value=100,
            value=20,
        )
        create_batch = st.form_submit_button("Build Batch")

    if create_batch:
        try:
            result = batch_selection_service.select_batch(
                candidate_id,
                requested_count=int(requested_count),
                matching_threshold=matching_threshold,
                fallback_score=fallback_score,
            )
            st.session_state["selected_application_batch"] = result.batch_id
            st.success(
                f"Batch {result.batch_id} created with "
                f"{result.selected_count} job(s)."
            )
        except (ValueError, SQLAlchemyError) as exc:
            st.error(f"Could not build batch: {exc}")

    batches = batch_selection_service.get_batches(candidate_id)
    if not batches:
        st.info("No application batches have been created for this candidate.")
        return

    batch_options = {
        f"Batch {batch.id} - {batch.status} ({batch.selected_count} jobs)": batch.id
        for batch in batches
    }
    current_batch_id = st.session_state.get("selected_application_batch")
    default_index = next(
        (
            index
            for index, batch_id in enumerate(batch_options.values())
            if batch_id == current_batch_id
        ),
        0,
    )
    selected_batch = st.selectbox(
        "Application batch",
        options=list(batch_options.keys()),
        index=default_index,
        key="batch_review_selection",
    )
    batch_id = batch_options[selected_batch]
    batch = next(item for item in batches if item.id == batch_id)
    rows = batch_selection_service.get_batch_applications(batch_id, candidate_id)

    if not rows:
        st.info("This batch contains no eligible jobs.")
        return

    st.caption(
        "Jobs are grouped by progressive relaxation stage and ranked by the "
        "existing explainable match score. Candidate skills are never inferred."
    )
    for application, job in rows:
        with st.container(border=True):
            st.markdown(f"### {application.selected_rank}. {job.title}")
            st.write(f"**Company:** {job.company} | **Source:** {job.source}")
            st.write(
                f"**Match:** {application.match_score}/100 | "
                f"**Selection stage:** {application.match_stage}"
            )
            st.write(f"**Location:** {job.location or 'Not specified'}")
            if job.required_skills:
                st.write(f"**Required skills:** {job.required_skills}")
            if application.source_url:
                st.link_button("Open Job", application.source_url)

    if batch.status == "draft":
        approve_column, cancel_column = st.columns(2)
        with approve_column:
            approve = st.button(
                "Approve This Batch",
                key=f"approve_batch_{batch.id}",
            )
        with cancel_column:
            cancel = st.button(
                "Cancel Draft Batch",
                key=f"cancel_batch_{batch.id}",
            )
        if approve:
            try:
                batch_selection_service.approve_batch(batch.id, candidate_id)
                st.success(
                    "Batch approved. Applications can now be prepared; "
                    "external submission still requires candidate control."
                )
                st.rerun()
            except (ValueError, SQLAlchemyError) as exc:
                st.error(f"Could not approve batch: {exc}")
        if cancel:
            try:
                batch_selection_service.cancel_batch(batch.id, candidate_id)
                st.success(
                    "Draft batch cancelled. Its application history is retained."
                )
                st.rerun()
            except (ValueError, SQLAlchemyError) as exc:
                st.error(f"Could not cancel batch: {exc}")
    if batch.status != "draft":
        st.success(f"Batch status: {batch.status}")

    if st.button("Prepare Packets for This Batch", key=f"prepare_packets_{batch.id}"):
        prepared = 0
        errors = []
        for application, _job in rows:
            try:
                application_packet_service.prepare_packet(
                    candidate_id=candidate_id, application_id=application.id
                )
                prepared += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Application {application.id}: {exc}")
        st.success(f"Prepared {prepared} application packet(s).")
        if errors:
            for error in errors:
                st.error(error)

    if st.button("Prepare Packets + Tailor in Parallel", key=f"prepare_parallel_{batch.id}"):
        with st.spinner("Preparing packets and tailored drafts in parallel..."):
            results = application_preparation_service.prepare_batch(
                candidate_id=candidate_id,
                application_ids=[application.id for application, _job in rows],
            )
        ok = [r for r in results if not r["error"]]
        bad = [r for r in results if r["error"]]
        st.success(f"Prepared {len(ok)} application(s) in parallel.")
        for r in bad:
            st.error(f"Application {r['application_id']}: {r['error']}")


if __name__ == "__main__":
    show_batch_review_page()
