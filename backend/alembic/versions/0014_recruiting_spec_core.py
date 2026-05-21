"""recruiting spec core: search states, presentations, profiles, prefs, hub

Revision ID: 0014_recruiting_spec_core
Revises: 0013_organizations
Create Date: 2026-05-21
"""

from alembic import op
import sqlalchemy as sa


revision = "0014_recruiting_spec_core"
down_revision = "0013_organizations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("searches", sa.Column("deactivated_at", sa.DateTime(), nullable=True))
    op.add_column("searches", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.add_column("searches", sa.Column("closed_at", sa.DateTime(), nullable=True))
    op.add_column("searches", sa.Column("assigned_talent_user_id", sa.Integer(), nullable=True))
    op.add_column("searches", sa.Column("alert_stale_days", sa.Integer(), nullable=True))
    op.add_column("searches", sa.Column("alert_no_response_days", sa.Integer(), nullable=True))
    op.add_column("searches", sa.Column("placed_candidate_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_searches_assigned_talent_user_id",
        "searches",
        "users",
        ["assigned_talent_user_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_searches_placed_candidate_id",
        "searches",
        "candidates",
        ["placed_candidate_id"],
        ["id"],
    )

    op.add_column("candidates", sa.Column("source", sa.String(length=30), nullable=True))

    op.add_column("candidate_notes", sa.Column("note_type", sa.String(length=40), nullable=True))
    op.add_column("candidate_notes", sa.Column("search_id", sa.Integer(), nullable=True))
    op.add_column("candidate_notes", sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.create_foreign_key("fk_candidate_notes_search_id", "candidate_notes", "searches", ["search_id"], ["id"])

    op.create_table(
        "candidate_presentations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("search_id", sa.Integer(), nullable=False),
        sa.Column("presented_by", sa.Integer(), nullable=False),
        sa.Column("presented_at", sa.DateTime(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["presented_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["search_id"], ["searches.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "search_id", name="uq_candidate_presentation"),
    )
    op.create_index("ix_candidate_presentations_candidate_id", "candidate_presentations", ["candidate_id"])
    op.create_index("ix_candidate_presentations_search_id", "candidate_presentations", ["search_id"])

    op.create_table(
        "client_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("industry", sa.String(length=200), nullable=True),
        sa.Column("company_size", sa.String(length=100), nullable=True),
        sa.Column("culture", sa.Text(), nullable=True),
        sa.Column("benefits", sa.Text(), nullable=True),
        sa.Column("work_mode", sa.String(length=50), nullable=True),
        sa.Column("tech_stack_json", sa.JSON(), nullable=True),
        sa.Column("frequent_requirements_json", sa.JSON(), nullable=True),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id"),
    )

    op.create_table(
        "client_contacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("role_title", sa.String(length=200), nullable=True),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_client_contacts_client_id", "client_contacts", ["client_id"])

    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("notification_settings_json", sa.JSON(), nullable=True),
        sa.Column("reminder_settings_json", sa.JSON(), nullable=True),
        sa.Column("default_stale_search_days", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("default_no_response_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "alert_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.Column("search_id", sa.Integer(), nullable=True),
        sa.Column("candidate_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("delivered_app", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("delivered_email", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["search_id"], ["searches.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alert_logs_event_type", "alert_logs", ["event_type"])
    op.create_index("ix_alert_logs_created_at", "alert_logs", ["created_at"])

    op.create_table(
        "meeting_integrations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.Column("conversation_type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversations_organization_id", "conversations", ["organization_id"])
    op.create_index("ix_conversations_client_id", "conversations", ["client_id"])

    op.create_table(
        "conversation_participants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", "user_id", name="uq_conversation_participant"),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    op.create_table(
        "conversation_summaries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("action_items_json", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE searches SET manual_state = 'desactivada', deactivated_at = now()
            WHERE manual_state = 'cerrada' AND archived_at IS NULL
            """
        )
    )
    conn.execute(sa.text("UPDATE searches SET updated_at = created_at WHERE updated_at IS NULL"))


def downgrade() -> None:
    op.drop_table("conversation_summaries")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")
    op.drop_table("conversation_participants")
    op.drop_index("ix_conversations_client_id", table_name="conversations")
    op.drop_index("ix_conversations_organization_id", table_name="conversations")
    op.drop_table("conversations")
    op.drop_table("meeting_integrations")
    op.drop_index("ix_alert_logs_created_at", table_name="alert_logs")
    op.drop_index("ix_alert_logs_event_type", table_name="alert_logs")
    op.drop_table("alert_logs")
    op.drop_table("user_preferences")
    op.drop_index("ix_client_contacts_client_id", table_name="client_contacts")
    op.drop_table("client_contacts")
    op.drop_table("client_profiles")
    op.drop_index("ix_candidate_presentations_search_id", table_name="candidate_presentations")
    op.drop_index("ix_candidate_presentations_candidate_id", table_name="candidate_presentations")
    op.drop_table("candidate_presentations")
    op.drop_constraint("fk_candidate_notes_search_id", "candidate_notes", type_="foreignkey")
    op.drop_column("candidate_notes", "is_pinned")
    op.drop_column("candidate_notes", "search_id")
    op.drop_column("candidate_notes", "note_type")
    op.drop_column("candidates", "source")
    op.drop_constraint("fk_searches_placed_candidate_id", "searches", type_="foreignkey")
    op.drop_constraint("fk_searches_assigned_talent_user_id", "searches", type_="foreignkey")
    op.drop_column("searches", "placed_candidate_id")
    op.drop_column("searches", "alert_no_response_days")
    op.drop_column("searches", "alert_stale_days")
    op.drop_column("searches", "assigned_talent_user_id")
    op.drop_column("searches", "closed_at")
    op.drop_column("searches", "updated_at")
    op.drop_column("searches", "deactivated_at")
