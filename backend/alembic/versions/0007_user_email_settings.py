"""user email settings

Revision ID: 0007_user_email_settings
Revises: 0006_product_upgrade
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa


revision = '0007_user_email_settings'
down_revision = '0006_product_upgrade'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_email_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('smtp_host', sa.String(length=255), nullable=True),
        sa.Column('smtp_port', sa.Integer(), nullable=False),
        sa.Column('smtp_user', sa.String(length=255), nullable=True),
        sa.Column('smtp_password', sa.String(length=500), nullable=True),
        sa.Column('smtp_from_email', sa.String(length=255), nullable=True),
        sa.Column('use_tls', sa.Boolean(), nullable=False),
        sa.Column('is_configured', sa.Boolean(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_user_email_settings_user_id', 'user_email_settings', ['user_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_user_email_settings_user_id', table_name='user_email_settings')
    op.drop_table('user_email_settings')
