"""candidate search assignments

Revision ID: 0015_candidate_assign
Revises: 0014_recruiting_spec_core
Create Date: 2026-05-21
"""

from alembic import op
import sqlalchemy as sa


revision = "0015_candidate_assign"
down_revision = "0014_recruiting_spec_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidate_search_assignments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("search_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="en_revision"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("assigned_by_user_id", sa.Integer(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["search_id"], ["searches.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "search_id", name="uq_candidate_search_assignment_pair"),
    )
    op.create_index("ix_candidate_search_assignments_candidate_id", "candidate_search_assignments", ["candidate_id"])
    op.create_index("ix_candidate_search_assignments_search_id", "candidate_search_assignments", ["search_id"])

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO candidate_search_assignments (candidate_id, search_id, status, assigned_at)
            SELECT id, search_id, COALESCE(status, 'en_revision'), COALESCE(created_at, now())
            FROM candidates
            WHERE search_id IS NOT NULL
            ON CONFLICT (candidate_id, search_id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_search_assignments_search_id", table_name="candidate_search_assignments")
    op.drop_index("ix_candidate_search_assignments_candidate_id", table_name="candidate_search_assignments")
    op.drop_table("candidate_search_assignments")
