"""add arcade_wallets table

Arcade-only coin wallet + shop inventory (skins / permanent powers / extra
starting life / daily-run retry). Coins are minted only by the validated
daily run and never convert to anything money-adjacent.

NOTE: init_db's create_all also builds this table on restart — if the table
already exists, `alembic stamp head` instead of `upgrade` (same drill as
admin_audit_logs / arcade_flags).

Revision ID: b7d2e9f1c3a5
Revises: a3e91b7c44d0
Create Date: 2026-07-07 03:20:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b7d2e9f1c3a5'
down_revision: Union[str, Sequence[str], None] = 'a3e91b7c44d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'arcade_wallets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, unique=True),
        sa.Column('coins', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('equipped_skin', sa.String(length=24), nullable=False, server_default='default'),
        sa.Column('owned_skins', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('owned_powers', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('extra_lives', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('coins_earned_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('arcade_wallets')
