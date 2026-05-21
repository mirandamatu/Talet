"""recruiting ia modules core tables

Revision ID: 0009_recruiting_ia_modules
Revises: 0008_calendar_invites
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_recruiting_ia_modules"
down_revision = "0008_calendar_invites"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_candidate_analyses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("search_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("match_score", sa.Float(), nullable=True),
        sa.Column("recommendation_level", sa.String(length=20), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("reasons_json", sa.JSON(), nullable=True),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=80), nullable=True),
        sa.Column("last_analyzed_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["search_id"], ["searches.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("search_id", "candidate_id", name="uq_search_candidate_analysis_pair"),
    )
    op.create_index(op.f("ix_search_candidate_analyses_search_id"), "search_candidate_analyses", ["search_id"], unique=False)
    op.create_index(op.f("ix_search_candidate_analyses_candidate_id"), "search_candidate_analyses", ["candidate_id"], unique=False)
    op.create_index(op.f("ix_search_candidate_analyses_source_hash"), "search_candidate_analyses", ["source_hash"], unique=False)

    op.create_table(
        "candidate_outreach",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("search_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("sent_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["search_id"], ["searches.id"]),
        sa.ForeignKeyConstraint(["sent_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_candidate_outreach_kind"), "candidate_outreach", ["kind"], unique=False)
    op.create_index(op.f("ix_candidate_outreach_status"), "candidate_outreach", ["status"], unique=False)
    op.create_index(op.f("ix_candidate_outreach_candidate_id"), "candidate_outreach", ["candidate_id"], unique=False)
    op.create_index(op.f("ix_candidate_outreach_search_id"), "candidate_outreach", ["search_id"], unique=False)

    op.create_table(
        "candidate_outreach_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("outreach_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("search_id", sa.Integer(), nullable=True),
        sa.Column("token", sa.String(length=120), nullable=False),
        sa.Column("action_type", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("used_payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["outreach_id"], ["candidate_outreach.id"]),
        sa.ForeignKeyConstraint(["search_id"], ["searches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_candidate_outreach_tokens_action_type"), "candidate_outreach_tokens", ["action_type"], unique=False)
    op.create_index(op.f("ix_candidate_outreach_tokens_candidate_id"), "candidate_outreach_tokens", ["candidate_id"], unique=False)
    op.create_index(op.f("ix_candidate_outreach_tokens_outreach_id"), "candidate_outreach_tokens", ["outreach_id"], unique=False)
    op.create_index(op.f("ix_candidate_outreach_tokens_search_id"), "candidate_outreach_tokens", ["search_id"], unique=False)
    op.create_index(op.f("ix_candidate_outreach_tokens_token"), "candidate_outreach_tokens", ["token"], unique=True)

    op.create_table(
        "candidate_notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("author_user_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_candidate_notes_candidate_id"), "candidate_notes", ["candidate_id"], unique=False)
    op.create_index(op.f("ix_candidate_notes_author_user_id"), "candidate_notes", ["author_user_id"], unique=False)

    op.create_table(
        "candidate_note_visibility",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("note_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["note_id"], ["candidate_notes.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_candidate_note_visibility_note_id"), "candidate_note_visibility", ["note_id"], unique=False)
    op.create_index(op.f("ix_candidate_note_visibility_role"), "candidate_note_visibility", ["role"], unique=False)
    op.create_index(op.f("ix_candidate_note_visibility_user_id"), "candidate_note_visibility", ["user_id"], unique=False)

    op.create_table(
        "google_calendar_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("google_email", sa.String(length=255), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_google_calendar_connections_user_id"), "google_calendar_connections", ["user_id"], unique=True)

    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_activity_logs_action"), "activity_logs", ["action"], unique=False)
    op.create_index(op.f("ix_activity_logs_actor_user_id"), "activity_logs", ["actor_user_id"], unique=False)
    op.create_index(op.f("ix_activity_logs_entity_id"), "activity_logs", ["entity_id"], unique=False)
    op.create_index(op.f("ix_activity_logs_entity_type"), "activity_logs", ["entity_type"], unique=False)

    op.create_table(
        "interview_transcripts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("interview_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_interview_transcripts_candidate_id"), "interview_transcripts", ["candidate_id"], unique=False)
    op.create_index(op.f("ix_interview_transcripts_interview_id"), "interview_transcripts", ["interview_id"], unique=False)
    op.create_index(op.f("ix_interview_transcripts_source_type"), "interview_transcripts", ["source_type"], unique=False)

    op.add_column("calendar_events", sa.Column("status", sa.String(length=40), nullable=True))
    op.add_column("calendar_events", sa.Column("organizer_email", sa.String(length=255), nullable=True))
    op.add_column("calendar_events", sa.Column("google_event_id", sa.String(length=255), nullable=True))
    op.add_column("interviews", sa.Column("calendar_event_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_interviews_calendar_event_id",
        "interviews",
        "calendar_events",
        ["calendar_event_id"],
        ["id"],
    )

    op.execute("UPDATE calendar_events SET status = 'confirmed' WHERE status IS NULL")
    op.alter_column("calendar_events", "status", nullable=False, existing_type=sa.String(length=40))


def downgrade() -> None:
    op.drop_constraint("fk_interviews_calendar_event_id", "interviews", type_="foreignkey")
    op.drop_column("interviews", "calendar_event_id")
    op.drop_column("calendar_events", "google_event_id")
    op.drop_column("calendar_events", "organizer_email")
    op.drop_column("calendar_events", "status")

    op.drop_index(op.f("ix_interview_transcripts_source_type"), table_name="interview_transcripts")
    op.drop_index(op.f("ix_interview_transcripts_interview_id"), table_name="interview_transcripts")
    op.drop_index(op.f("ix_interview_transcripts_candidate_id"), table_name="interview_transcripts")
    op.drop_table("interview_transcripts")

    op.drop_index(op.f("ix_activity_logs_entity_type"), table_name="activity_logs")
    op.drop_index(op.f("ix_activity_logs_entity_id"), table_name="activity_logs")
    op.drop_index(op.f("ix_activity_logs_actor_user_id"), table_name="activity_logs")
    op.drop_index(op.f("ix_activity_logs_action"), table_name="activity_logs")
    op.drop_table("activity_logs")

    op.drop_index(op.f("ix_google_calendar_connections_user_id"), table_name="google_calendar_connections")
    op.drop_table("google_calendar_connections")

    op.drop_index(op.f("ix_candidate_note_visibility_user_id"), table_name="candidate_note_visibility")
    op.drop_index(op.f("ix_candidate_note_visibility_role"), table_name="candidate_note_visibility")
    op.drop_index(op.f("ix_candidate_note_visibility_note_id"), table_name="candidate_note_visibility")
    op.drop_table("candidate_note_visibility")

    op.drop_index(op.f("ix_candidate_notes_author_user_id"), table_name="candidate_notes")
    op.drop_index(op.f("ix_candidate_notes_candidate_id"), table_name="candidate_notes")
    op.drop_table("candidate_notes")

    op.drop_index(op.f("ix_candidate_outreach_tokens_token"), table_name="candidate_outreach_tokens")
    op.drop_index(op.f("ix_candidate_outreach_tokens_search_id"), table_name="candidate_outreach_tokens")
    op.drop_index(op.f("ix_candidate_outreach_tokens_outreach_id"), table_name="candidate_outreach_tokens")
    op.drop_index(op.f("ix_candidate_outreach_tokens_candidate_id"), table_name="candidate_outreach_tokens")
    op.drop_index(op.f("ix_candidate_outreach_tokens_action_type"), table_name="candidate_outreach_tokens")
    op.drop_table("candidate_outreach_tokens")

    op.drop_index(op.f("ix_candidate_outreach_search_id"), table_name="candidate_outreach")
    op.drop_index(op.f("ix_candidate_outreach_candidate_id"), table_name="candidate_outreach")
    op.drop_index(op.f("ix_candidate_outreach_status"), table_name="candidate_outreach")
    op.drop_index(op.f("ix_candidate_outreach_kind"), table_name="candidate_outreach")
    op.drop_table("candidate_outreach")

    op.drop_index(op.f("ix_search_candidate_analyses_source_hash"), table_name="search_candidate_analyses")
    op.drop_index(op.f("ix_search_candidate_analyses_candidate_id"), table_name="search_candidate_analyses")
    op.drop_index(op.f("ix_search_candidate_analyses_search_id"), table_name="search_candidate_analyses")
    op.drop_table("search_candidate_analyses")
