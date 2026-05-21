"""organizations multi-tenancy

Revision ID: 0013_organizations
Revises: 0012_client_plan
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_organizations"
down_revision = "0012_client_plan"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("primary_color", sa.String(length=20), nullable=True),
        sa.Column("plan", sa.String(length=20), nullable=False, server_default="starter"),
        sa.Column("plan_status", sa.String(length=20), nullable=False, server_default="trial"),
        sa.Column("trial_ends_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    op.add_column("users", sa.Column("organization_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_users_organization_id", "users", "organizations", ["organization_id"], ["id"])
    op.create_index("ix_users_organization_id", "users", ["organization_id"])

    op.add_column("clients", sa.Column("organization_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_clients_organization_id", "clients", "organizations", ["organization_id"], ["id"])
    op.create_index("ix_clients_organization_id", "clients", ["organization_id"])

    op.add_column("candidates", sa.Column("client_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_candidates_client_id", "candidates", "clients", ["client_id"], ["id"])
    op.create_index("ix_candidates_client_id", "candidates", ["client_id"])

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO organizations (name, slug, plan, plan_status, created_at)
            VALUES ('Default', 'aptia-default', 'starter', 'trial', now())
            """
        )
    )
    default_org_id = conn.execute(sa.text("SELECT id FROM organizations WHERE slug = 'aptia-default' LIMIT 1")).scalar()

    conn.execute(sa.text("UPDATE users SET organization_id = :oid WHERE organization_id IS NULL"), {"oid": default_org_id})
    conn.execute(sa.text("UPDATE clients SET organization_id = :oid WHERE organization_id IS NULL"), {"oid": default_org_id})

    conn.execute(
        sa.text(
            """
            UPDATE candidates AS c
            SET client_id = s.client_id
            FROM searches AS s
            WHERE c.search_id = s.id AND c.client_id IS NULL
            """
        )
    )

    op.alter_column("organizations", "plan", server_default=None)
    op.alter_column("organizations", "plan_status", server_default=None)
    op.alter_column("organizations", "created_at", server_default=None)


def downgrade() -> None:
    op.drop_constraint("fk_candidates_client_id", "candidates", type_="foreignkey")
    op.drop_index("ix_candidates_client_id", table_name="candidates")
    op.drop_column("candidates", "client_id")

    op.drop_constraint("fk_clients_organization_id", "clients", type_="foreignkey")
    op.drop_index("ix_clients_organization_id", table_name="clients")
    op.drop_column("clients", "organization_id")

    op.drop_constraint("fk_users_organization_id", "users", type_="foreignkey")
    op.drop_index("ix_users_organization_id", table_name="users")
    op.drop_column("users", "organization_id")

    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")
