"""product upgrade persistence

Revision ID: 0006_product_upgrade
Revises: 0005_ai_insights
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa


revision = '0006_product_upgrade'
down_revision = '0005_ai_insights'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('searches', sa.Column('archived_at', sa.DateTime(), nullable=True))
    op.add_column('candidates', sa.Column('email', sa.String(length=200), nullable=True))
    op.add_column('candidates', sa.Column('cv_file_name', sa.String(length=255), nullable=True))
    op.add_column('candidates', sa.Column('cv_uploaded_at', sa.DateTime(), nullable=True))
    op.alter_column('candidates', 'search_id', existing_type=sa.Integer(), nullable=True)
    op.alter_column('candidates', 'cv_file_url', existing_type=sa.String(length=500), nullable=True)

    op.create_table(
        'search_documents',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('search_id', sa.Integer(), sa.ForeignKey('searches.id'), nullable=False),
        sa.Column('kind', sa.String(length=50), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_url', sa.String(length=500), nullable=False),
        sa.Column('content_type', sa.String(length=120), nullable=True),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_search_documents_search_id', 'search_documents', ['search_id'])

    op.create_table(
        'search_ai_questions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('search_id', sa.Integer(), sa.ForeignKey('searches.id'), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('answered_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_search_ai_questions_search_id', 'search_ai_questions', ['search_id'])

    op.create_table(
        'calendar_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('start_datetime', sa.DateTime(), nullable=False),
        sa.Column('end_datetime', sa.DateTime(), nullable=False),
        sa.Column('kind', sa.String(length=50), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('role_scope', sa.String(length=50), nullable=True),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id'), nullable=True),
        sa.Column('search_id', sa.Integer(), sa.ForeignKey('searches.id'), nullable=True),
        sa.Column('candidate_id', sa.Integer(), sa.ForeignKey('candidates.id'), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_calendar_events_client_id', 'calendar_events', ['client_id'])
    op.create_index('ix_calendar_events_search_id', 'calendar_events', ['search_id'])


def downgrade() -> None:
    op.drop_index('ix_calendar_events_search_id', table_name='calendar_events')
    op.drop_index('ix_calendar_events_client_id', table_name='calendar_events')
    op.drop_table('calendar_events')
    op.drop_index('ix_search_ai_questions_search_id', table_name='search_ai_questions')
    op.drop_table('search_ai_questions')
    op.drop_index('ix_search_documents_search_id', table_name='search_documents')
    op.drop_table('search_documents')
    op.alter_column('candidates', 'cv_file_url', existing_type=sa.String(length=500), nullable=False)
    op.alter_column('candidates', 'search_id', existing_type=sa.Integer(), nullable=False)
    op.drop_column('candidates', 'cv_uploaded_at')
    op.drop_column('candidates', 'cv_file_name')
    op.drop_column('candidates', 'email')
    op.drop_column('searches', 'archived_at')
