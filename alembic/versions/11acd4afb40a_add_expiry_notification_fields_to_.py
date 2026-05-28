"""add expiry notification fields to subscription

Revision ID: 11acd4afb40a
Revises: 2ff6ade5ec1e
Create Date: 2025-07-03 00:56:06.791870

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '11acd4afb40a'
down_revision: Union[str, Sequence[str], None] = '2ff6ade5ec1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    from sqlalchemy import Boolean, Column
    op.add_column('subscriptions', sa.Column('imminent_expiry_notified', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('subscriptions', sa.Column('expired_notified', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('subscriptions', 'imminent_expiry_notified')
    op.drop_column('subscriptions', 'expired_notified')
