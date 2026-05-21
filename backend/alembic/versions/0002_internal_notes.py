"""add internal notes to searches and candidates

Revision ID: 0004_internal_notes
Revises: 0003_user_clients
Create Date: 2026-02-21

"""
from alembic import op
import sqlalchemy as sa

revision = "0004_internal_notes"
down_revision = "0003_user_clients"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("searches", sa.Column("internal_notes", sa.Text(), nullable=True))
    op.add_column("candidates", sa.Column("internal_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("candidates", "internal_notes")
    op.drop_column("searches", "internal_notes")
