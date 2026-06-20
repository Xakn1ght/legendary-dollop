"""charge_request credit_used and renewal intent

Adds money-safety columns to charge_requests:
- credit_used: wallet credit reserved at order creation, refunded on cancel/deny
- renewal_template / renewal_price: auto-renew intent captured at order time and
  applied to the subscription only when the charge is approved

Revision ID: 5abf85a96cd2
Revises: 9d8b1c2e3f4a
Create Date: 2026-06-11 11:35:31.202687

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5abf85a96cd2'
down_revision: Union[str, Sequence[str], None] = '9d8b1c2e3f4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('charge_requests', sa.Column('credit_used', sa.Integer(), nullable=True))
    op.add_column('charge_requests', sa.Column('renewal_template', sa.String(), nullable=True))
    op.add_column('charge_requests', sa.Column('renewal_price', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('charge_requests', 'renewal_price')
    op.drop_column('charge_requests', 'renewal_template')
    op.drop_column('charge_requests', 'credit_used')
