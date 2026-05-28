"""add expiry notification fields to subscription

Revision ID: 2ff6ade5ec1e
Revises: fb88567f39b4
Create Date: 2025-07-03 00:54:21.707476

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2ff6ade5ec1e'
down_revision: Union[str, Sequence[str], None] = 'fb88567f39b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
