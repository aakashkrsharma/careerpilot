"""Add Phase 8 application management tables.

Revision ID: 0001_phase8
Revises:
Create Date: 2026-11-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "0001_phase8"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_application_batches(bind) -> None:
    inspector = inspect(bind)
    if inspector.has_table("application_batches"):
        return
    op.create_table(
        "application_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("requested_count", sa.Integer(), nullable=False),
        sa.Column("selected_count", sa.Integer(), nullable=False),
        sa.Column("matching_threshold", sa.Integer()),
        sa.Column("relaxation_stages", sa.Text()),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("approved_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
    )


def _create_applications(bind) -> None:
    inspector = inspect(bind)
    if inspector.has_table("applications"):
        return
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("tailored_resume_id", sa.Integer()),
        sa.Column("application_batch_id", sa.Integer()),
        sa.Column("dedup_key", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("source_url", sa.String()),
        sa.Column("source_external_id", sa.String()),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("execution_mode", sa.String(), nullable=False),
        sa.Column("match_score", sa.Integer()),
        sa.Column("match_stage", sa.String()),
        sa.Column("selected_rank", sa.Integer()),
        sa.Column("discovered_at", sa.DateTime()),
        sa.Column("tailored_at", sa.DateTime()),
        sa.Column("clarification_at", sa.DateTime()),
        sa.Column("ready_at", sa.DateTime()),
        sa.Column("submitted_at", sa.DateTime()),
        sa.Column("applied_at", sa.DateTime()),
        sa.Column("follow_up_at", sa.DateTime()),
        sa.Column("external_application_id", sa.String()),
        sa.Column("manual_instructions", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(["tailored_resume_id"], ["tailored_resumes.id"]),
        sa.ForeignKeyConstraint(["application_batch_id"], ["application_batches.id"]),
        sa.UniqueConstraint("candidate_id", "dedup_key", name="uq_application_candidate_dedup"),
    )


def _create_answer_bank(bind) -> None:
    inspector = inspect(bind)
    if inspector.has_table("candidate_answer_bank"):
        return
    op.create_table(
        "candidate_answer_bank",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("canonical_key", sa.String(), nullable=False),
        sa.Column("aliases", sa.Text()),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("scope_value", sa.String(), nullable=False),
        sa.Column("sensitivity", sa.String(), nullable=False),
        sa.Column("is_approved", sa.Boolean(), nullable=False),
        sa.Column("source_application_id", sa.Integer()),
        sa.Column("approved_at", sa.DateTime()),
        sa.Column("expires_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["source_application_id"], ["applications.id"]),
        sa.UniqueConstraint(
            "candidate_id",
            "canonical_key",
            "scope",
            "scope_value",
            name="uq_answer_bank_candidate_key_scope",
        ),
    )


def _create_clarification_requests(bind) -> None:
    inspector = inspect(bind)
    if inspector.has_table("clarification_requests"):
        return
    op.create_table(
        "clarification_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("canonical_key", sa.String(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("proposed_answer", sa.Text()),
        sa.Column("candidate_answer", sa.Text()),
        sa.Column("category", sa.String()),
        sa.Column("sensitivity", sa.String(), nullable=False),
        sa.Column("save_to_answer_bank", sa.Boolean(), nullable=False),
        sa.Column("is_resolved", sa.Boolean(), nullable=False),
        sa.Column("resolved_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime()),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
    )


def _create_status_events(bind) -> None:
    inspector = inspect(bind)
    if inspector.has_table("application_status_events"):
        return
    op.create_table(
        "application_status_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String()),
        sa.Column("to_status", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("metadata_json", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
    )


def upgrade() -> None:
    bind = op.get_bind()
    _create_application_batches(bind)
    _create_applications(bind)
    _create_answer_bank(bind)
    _create_clarification_requests(bind)
    _create_status_events(bind)

    for table_name, columns in (
        ("applications", ("candidate_id", "status", "dedup_key", "job_id")),
        ("candidate_answer_bank", ("candidate_id", "canonical_key", "scope", "scope_value")),
        ("application_status_events", ("application_id", "created_at")),
        ("clarification_requests", ("application_id", "is_resolved")),
    ):
        inspector = inspect(bind)
        existing = {index["name"] for index in inspector.get_indexes(table_name)}
        for column_name in columns:
            index_name = f"ix_{table_name}_{column_name}"
            if index_name not in existing:
                op.create_index(index_name, table_name, [column_name], unique=False)


def downgrade() -> None:
    op.drop_table("application_status_events")
    op.drop_table("clarification_requests")
    op.drop_table("candidate_answer_bank")
    op.drop_table("applications")
    op.drop_table("application_batches")
