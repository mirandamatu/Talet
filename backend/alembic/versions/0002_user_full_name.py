"""add user full_name

Revision ID: 0002_user_full_name
Revises: 0001_init
Create Date: 2026-02-12

"""
from alembic import op
import sqlalchemy as sa


revision = "0002_user_full_name"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "full_name")
