"""cashout payout receipt columns

mark_cashout_paid always wrote receipt_file_id / receipt_message_id, but the
columns never existed on cashout_requests, so the payout proof was silently
dropped. Additive only — autogenerate also proposed dropping hand-made
performance indexes and legacy users columns (DB/model drift); those were
deliberately removed from this migration.

Revision ID: 6ed7490e5552
Revises: 7e0a8aad6c31
Create Date: 2026-07-18 21:08:34.531878

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6ed7490e5552'
down_revision: Union[str, Sequence[str], None] = '7e0a8aad6c31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('cashout_requests', sa.Column('receipt_file_id', sa.String(), nullable=True))
    op.add_column('cashout_requests', sa.Column('receipt_message_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('cashout_requests', 'receipt_message_id')
    op.drop_column('cashout_requests', 'receipt_file_id')
