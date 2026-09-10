"""unique crm activity per policy_id + activity_type

Revision ID: 002_crm_policy_type_uq
Revises: 001_initial_persistence
Create Date: 2026-09-10 07:30:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_crm_policy_type_uq"
down_revision: Union[str, None] = "001_initial_persistence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_crm_activities_policy_type",
        "crm_activities",
        ["policy_id", "activity_type"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_crm_activities_policy_type", "crm_activities", type_="unique")
