"""add user_clients mapping

Revision ID: 0003_user_clients
Revises: 0002_user_full_name
Create Date: 2026-02-13

"""
from alembic import op
import sqlalchemy as sa


revision = "0003_user_clients"
down_revision = "0002_user_full_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_clients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("user_id", "client_id", name="uq_user_clients_user_client"),
    )
    op.create_index("ix_user_clients_user_id", "user_clients", ["user_id"])
    op.create_index("ix_user_clients_client_id", "user_clients", ["client_id"])

    op.execute(
        """
        INSERT INTO user_clients (user_id, client_id)
        SELECT id, client_id
        FROM users
        WHERE client_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_user_clients_client_id", table_name="user_clients")
    op.drop_index("ix_user_clients_user_id", table_name="user_clients")
    op.drop_table("user_clients")
