"""customers + environment ownership + connector type uniqueness

Revision ID: 003_customers_env
Revises: 002_crm_policy_type_uq
Create Date: 2026-09-10 08:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003_customers_env"
down_revision: Union[str, None] = "002_crm_policy_type_uq"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LEGACY_REF = "migration:003_customers_env"


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("external_ref", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column(
        "environments",
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    conn = op.get_bind()
    needs_backfill = conn.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM environments WHERE customer_id IS NULL)")
    ).scalar()
    if needs_backfill:
        legacy_id = conn.execute(
            sa.text("SELECT id FROM customers WHERE external_ref = :ref LIMIT 1"),
            {"ref": _LEGACY_REF},
        ).scalar()
        if legacy_id is None:
            legacy_id = uuid4()
            conn.execute(
                sa.text(
                    "INSERT INTO customers (id, name, external_ref) VALUES (:id, :name, :ref)"
                ),
                {
                    "id": legacy_id,
                    "name": "Legacy Unassigned",
                    "ref": _LEGACY_REF,
                },
            )
        conn.execute(
            sa.text(
                """
                UPDATE environments
                SET customer_id = :cid
                WHERE customer_id IS NULL
                """
            ),
            {"cid": legacy_id},
        )

    remaining = conn.execute(
        sa.text("SELECT COUNT(*) FROM environments WHERE customer_id IS NULL")
    ).scalar()
    if remaining:
        raise RuntimeError("environments.customer_id backfill incomplete")

    op.alter_column("environments", "customer_id", nullable=False)
    op.create_foreign_key(
        "fk_environments_customer_id",
        "environments",
        "customers",
        ["customer_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Deduplicate connectors before UNIQUE(environment_id, connector_type).
    # Keeps the earliest row per pair; does not touch jobs or crm_activities.
    op.execute(
        sa.text(
            """
            DELETE FROM connectors a
            USING connectors b
            WHERE a.environment_id = b.environment_id
              AND a.connector_type = b.connector_type
              AND (
                    a.created_at > b.created_at
                    OR (a.created_at = b.created_at AND a.id::text > b.id::text)
                  )
            """
        )
    )
    op.create_unique_constraint(
        "uq_connectors_env_type",
        "connectors",
        ["environment_id", "connector_type"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_connectors_env_type", "connectors", type_="unique")
    op.drop_constraint("fk_environments_customer_id", "environments", type_="foreignkey")
    op.drop_column("environments", "customer_id")
    op.drop_table("customers")
