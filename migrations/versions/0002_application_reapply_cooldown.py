"""Allow historical applications while preventing concurrent active duplicates.

Revision ID: 0002_reapply_cooldown
Revises: 0001_phase8
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "0002_reapply_cooldown"
down_revision: Union[str, Sequence[str], None] = "0001_phase8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ACTIVE_WHERE = (
    "status IN ('discovered', 'tailored', 'needs_clarification', "
    "'ready', 'submitted', 'manual_required')"
)
ACTIVE_INDEX = "uq_application_active_candidate_dedup"
LIFETIME_CONSTRAINT = "uq_application_candidate_dedup"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("applications"):
        return

    lifetime_constraints = {
        constraint.get("name")
        for constraint in inspector.get_unique_constraints("applications")
    }
    if LIFETIME_CONSTRAINT in lifetime_constraints:
        with op.batch_alter_table("applications", recreate="always") as batch:
            batch.drop_constraint(LIFETIME_CONSTRAINT, type_="unique")

    inspector = inspect(bind)
    existing_indexes = {
        index["name"] for index in inspector.get_indexes("applications")
    }
    if ACTIVE_INDEX not in existing_indexes:
        op.create_index(
            ACTIVE_INDEX,
            "applications",
            ["candidate_id", "dedup_key"],
            unique=True,
            sqlite_where=sa.text(ACTIVE_WHERE),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("applications"):
        return

    existing_indexes = {
        index["name"] for index in inspector.get_indexes("applications")
    }
    if ACTIVE_INDEX in existing_indexes:
        op.drop_index(ACTIVE_INDEX, table_name="applications")

    lifetime_constraints = {
        constraint.get("name")
        for constraint in inspect(bind).get_unique_constraints("applications")
    }
    if LIFETIME_CONSTRAINT not in lifetime_constraints:
        with op.batch_alter_table("applications", recreate="always") as batch:
            batch.create_unique_constraint(
                LIFETIME_CONSTRAINT,
                ["candidate_id", "dedup_key"],
            )
