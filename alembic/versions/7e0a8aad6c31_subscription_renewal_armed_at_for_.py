"""subscription renewal_armed_at for native next_plan

Revision ID: 7e0a8aad6c31
Revises: c4d8e17f52b3
Create Date: 2026-07-12 17:29:13.105952

Hand-trimmed: autogenerate also proposed dropping subscription_links, the
runtime-created idx_* indexes (database/indexes.py builds those outside
alembic) and two legacy users columns — long-standing model/DB drift that
must NOT be "fixed" by a feature migration. Only the new column ships.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7e0a8aad6c31'
down_revision: Union[str, Sequence[str], None] = 'c4d8e17f52b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('subscriptions', sa.Column('renewal_armed_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('subscriptions', 'renewal_armed_at')
