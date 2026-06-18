"""initial jobs table

Revision ID: 0001
Revises:
Create Date: 2026-06-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("raw_key", sa.String(length=255), nullable=False),
        sa.Column("prompt", sa.String(length=1024), nullable=False),
        sa.Column("annotated_key", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("mask_count", sa.Integer(), nullable=True),
        sa.Column("processing_ms", sa.Integer(), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_uploaded_at", "jobs", ["uploaded_at"])


def downgrade() -> None:
    op.drop_index("ix_jobs_uploaded_at", table_name="jobs")
    op.drop_table("jobs")
