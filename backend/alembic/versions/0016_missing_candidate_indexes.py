"""add missing candidate indexes

Revision ID: 0016_missing_candidate_indexes
Revises: 0015_candidate_assign
Create Date: 2026-05-21
"""

from alembic import op


revision = "0016_missing_candidate_indexes"
down_revision = "0015_candidate_assign"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_candidates_search_id", "candidates", ["search_id"])
    op.create_index("ix_candidates_archived_at", "candidates", ["archived_at"])
    op.create_index("ix_candidate_search_assignments_archived_at", "candidate_search_assignments", ["archived_at"])
    op.create_index("ix_status_history_candidate_id", "status_history", ["candidate_id"])


def downgrade() -> None:
    op.drop_index("ix_status_history_candidate_id", table_name="status_history")
    op.drop_index("ix_candidate_search_assignments_archived_at", table_name="candidate_search_assignments")
    op.drop_index("ix_candidates_archived_at", table_name="candidates")
    op.drop_index("ix_candidates_search_id", table_name="candidates")
