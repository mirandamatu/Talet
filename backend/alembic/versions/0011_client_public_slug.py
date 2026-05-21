"""client public slug for career page

Revision ID: 0011_client_public_slug
Revises: 0010_search_manual_state
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_client_public_slug"
down_revision = "0010_search_manual_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("public_slug", sa.String(length=100), nullable=True))
    op.create_index("ix_clients_public_slug", "clients", ["public_slug"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_clients_public_slug", table_name="clients")
    op.drop_column("clients", "public_slug")
