"""extend jobs table for rag reindex queue

Revision ID: 20260302_0003
Revises: 20260227_0002
Create Date: 2026-03-02 10:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260302_0003"
down_revision: Union[str, Sequence[str], None] = "20260227_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("type", sa.String(length=32), nullable=False, server_default="generic"),
    )
    op.add_column("jobs", sa.Column("payload_json", sa.JSON(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "jobs",
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("3")),
    )
    op.add_column("jobs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("error", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("result_json", sa.JSON(), nullable=True))
    op.create_index("ix_jobs_type_status_created_at", "jobs", ["type", "status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_jobs_type_status_created_at", table_name="jobs")
    op.drop_column("jobs", "result_json")
    op.drop_column("jobs", "error")
    op.drop_column("jobs", "finished_at")
    op.drop_column("jobs", "started_at")
    op.drop_column("jobs", "max_attempts")
    op.drop_column("jobs", "attempts")
    op.drop_column("jobs", "payload_json")
    op.drop_column("jobs", "type")
