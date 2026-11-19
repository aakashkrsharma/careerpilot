"""Persist job-source configuration, health, provenance, and compensation units.

Revision ID: 0003_job_discovery
Revises: 0002_reapply_cooldown
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_job_discovery"
down_revision: Union[str, Sequence[str], None] = "0002_reapply_cooldown"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_columns = {
        column["name"] for column in sa.inspect(bind).get_columns("jobs")
    }
    for name, column_type in (
        ("salary_currency", sa.String(length=3)),
        ("salary_period", sa.String(length=20)),
        ("salary_text", sa.String()),
    ):
        if name not in existing_columns:
            op.add_column("jobs", sa.Column(name, column_type))

    op.create_table(
        "job_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(), nullable=False),
        sa.Column("connector_type", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column(
            "region_group",
            sa.String(),
            nullable=False,
            server_default="india",
        ),
        sa.Column("config_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "terms_approved",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column(
            "min_interval_seconds",
            sa.Integer(),
            nullable=False,
            server_default="3600",
        ),
        sa.Column("next_allowed_at", sa.DateTime()),
        sa.Column("last_run_at", sa.DateTime()),
        sa.Column("last_success_at", sa.DateTime()),
        sa.Column(
            "last_status",
            sa.String(),
            nullable=False,
            server_default="never_run",
        ),
        sa.Column("last_error", sa.Text()),
        sa.Column(
            "consecutive_failures",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "last_fetched_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "last_created_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "last_updated_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "last_duplicate_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "last_cooldown_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "last_excluded_region_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_sources_id", "job_sources", ["id"], unique=False)
    op.create_index(
        "ix_job_sources_source_key", "job_sources", ["source_key"], unique=True
    )
    op.create_index(
        "ix_job_sources_connector_type",
        "job_sources",
        ["connector_type"],
        unique=False,
    )
    op.create_index(
        "ix_job_sources_enabled", "job_sources", ["enabled"], unique=False
    )

    op.create_table(
        "job_source_listings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("listing_key", sa.String(), nullable=False),
        sa.Column("external_id", sa.String()),
        sa.Column("source_url", sa.String()),
        sa.Column("source_updated_at", sa.DateTime()),
        sa.Column(
            "first_seen_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["job_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "listing_key",
            name="uq_source_listing_key",
        ),
    )
    op.create_index(
        "ix_job_source_listings_id",
        "job_source_listings",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_job_source_listings_source_id",
        "job_source_listings",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        "ix_job_source_listings_job_id",
        "job_source_listings",
        ["job_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    existing_columns = {
        column["name"] for column in sa.inspect(bind).get_columns("jobs")
    }
    op.drop_index("ix_job_source_listings_job_id", table_name="job_source_listings")
    op.drop_index("ix_job_source_listings_source_id", table_name="job_source_listings")
    op.drop_index("ix_job_source_listings_id", table_name="job_source_listings")
    op.drop_table("job_source_listings")
    op.drop_index("ix_job_sources_enabled", table_name="job_sources")
    op.drop_index("ix_job_sources_connector_type", table_name="job_sources")
    op.drop_index("ix_job_sources_source_key", table_name="job_sources")
    op.drop_index("ix_job_sources_id", table_name="job_sources")
    op.drop_table("job_sources")
    for column_name in ("salary_text", "salary_period", "salary_currency"):
        if column_name in existing_columns:
            op.drop_column("jobs", column_name)
