"""user payout_card

NOTE: autogenerate also proposed dropping dozens of hand-created indexes,
users.discount_* and the subscription_links table (model↔DB drift that
predates this change). All of that was stripped — this migration only adds
the saved cash-out card column.

Revision ID: 86428ab35937
Revises: e4a7c92b8d10
Create Date: 2026-07-08 05:31:39.693484

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '86428ab35937'
down_revision: Union[str, Sequence[str], None] = 'e4a7c92b8d10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('payout_card', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'payout_card')
