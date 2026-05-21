"""plan columns on clients

Revision ID: 0012_client_plan
Revises: 0011_client_public_slug
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_client_plan"
down_revision = "0011_client_public_slug"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("plan", sa.String(length=20), nullable=False, server_default="starter"))
    op.add_column("clients", sa.Column("plan_status", sa.String(length=20), nullable=False, server_default="trial"))
    op.add_column("clients", sa.Column("trial_ends_at", sa.DateTime(), nullable=True))
    op.alter_column("clients", "plan", server_default=None)
    op.alter_column("clients", "plan_status", server_default=None)


def downgrade() -> None:
    op.drop_column("clients", "trial_ends_at")
    op.drop_column("clients", "plan_status")
    op.drop_column("clients", "plan")
