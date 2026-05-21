"""calendar invites and meeting links

Revision ID: 0008_calendar_invites
Revises: 0007_user_email_settings
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa


revision = '0008_calendar_invites'
down_revision = '0007_user_email_settings'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('calendar_events', sa.Column('meeting_url', sa.String(length=500), nullable=True))
    op.add_column('calendar_events', sa.Column('invite_emails_json', sa.JSON(), nullable=True))
    op.add_column('calendar_events', sa.Column('invited_user_ids_json', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('calendar_events', 'invited_user_ids_json')
    op.drop_column('calendar_events', 'invite_emails_json')
    op.drop_column('calendar_events', 'meeting_url')
