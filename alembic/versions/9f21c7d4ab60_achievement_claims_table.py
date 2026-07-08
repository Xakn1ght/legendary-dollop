"""achievement_claims table (mission achievements, 1GB coupon claims)

Revision ID: 9f21c7d4ab60
Revises: 86428ab35937
Create Date: 2026-07-08 07:55:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9f21c7d4ab60'
down_revision: Union[str, Sequence[str], None] = '86428ab35937'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'achievement_claims',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('achievement_key', sa.String(length=32), nullable=False),
        sa.Column('coupon_id', sa.Integer(), sa.ForeignKey('reward_coupons.id'), nullable=True),
        sa.Column('claimed_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('user_id', 'achievement_key', name='uq_achievement_claim_user_key'),
    )
    op.create_index('idx_achievement_claims_user', 'achievement_claims', ['user_id'])


def downgrade() -> None:
    op.drop_index('idx_achievement_claims_user', table_name='achievement_claims')
    op.drop_table('achievement_claims')
