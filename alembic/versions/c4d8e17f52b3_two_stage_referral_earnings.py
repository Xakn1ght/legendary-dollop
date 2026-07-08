"""two-stage referral earnings: cashback_balance + promoter_unlocked_at

Revision ID: c4d8e17f52b3
Revises: 9f21c7d4ab60
Create Date: 2026-07-08 15:20:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c4d8e17f52b3'
down_revision: Union[str, Sequence[str], None] = '9f21c7d4ab60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('cashback_balance', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('promoter_unlocked_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'promoter_unlocked_at')
    op.drop_column('users', 'cashback_balance')
