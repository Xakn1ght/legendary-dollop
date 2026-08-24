"""index subscriptions on (user_id, plan_name, created_at)

Free-trial eligibility is DERIVED from the subscriptions table (see
services/flows/free_tests.py), and the purchase menu now asks "may this user
take a trial?" on every render in order to hide the button on cooldown. The
table had no indexes at all, so that was a sequential scan per menu open.

Additive and reversible; index only, no data or column changes.

Revision ID: a1c4f7b20e93
Revises: 6ed7490e5552
Create Date: 2026-08-24

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1c4f7b20e93'
down_revision: Union[str, Sequence[str], None] = '6ed7490e5552'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "ix_subscriptions_user_plan_created"


def upgrade() -> None:
    op.create_index(
        INDEX_NAME,
        "subscriptions",
        ["user_id", "plan_name", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="subscriptions")
