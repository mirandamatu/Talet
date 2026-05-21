"""search manual state

Revision ID: 0010_search_manual_state
Revises: 0009_recruiting_ia_modules
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_search_manual_state"
down_revision = "0009_recruiting_ia_modules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("searches", sa.Column("manual_state", sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column("searches", "manual_state")
