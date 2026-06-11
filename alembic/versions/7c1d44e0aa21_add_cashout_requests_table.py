"""add cashout_requests table

The cash-out flow (dashboard wallet withdrawal) was wired end-to-end —
route registered, repos/cashout.py written — but the CashoutRequest model
and table never existed, so every request 500'd. This creates the table
the repository already expects.

Revision ID: 7c1d44e0aa21
Revises: 5abf85a96cd2
Create Date: 2026-06-11 12:05:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7c1d44e0aa21'
down_revision: Union[str, Sequence[str], None] = '5abf85a96cd2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'cashout_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('destination', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('requested_at', sa.DateTime(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('processed_by', sa.Integer(), nullable=True),
        sa.Column('admin_note', sa.String(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('cashout_requests')
