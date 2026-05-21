"""add ai insights table

Revision ID: 0005_ai_insights
Revises: 0004_internal_notes
Create Date: 2026-04-27

"""
from alembic import op
import sqlalchemy as sa


revision = "0005_ai_insights"
down_revision = "0004_internal_notes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_insights",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=80), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("recommendation", sa.Boolean(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ai_insights_entity_type", "ai_insights", ["entity_type"])
    op.create_index("ix_ai_insights_entity_id", "ai_insights", ["entity_id"])
    op.create_index("ix_ai_insights_kind", "ai_insights", ["kind"])


def downgrade() -> None:
    op.drop_index("ix_ai_insights_kind", table_name="ai_insights")
    op.drop_index("ix_ai_insights_entity_id", table_name="ai_insights")
    op.drop_index("ix_ai_insights_entity_type", table_name="ai_insights")
    op.drop_table("ai_insights")
