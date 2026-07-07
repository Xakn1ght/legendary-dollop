"""Telegram admin ids are int64 — widen approved_by/processed_by columns.

A 7.1e9 admin id overflowed int32 on VIP approve and rolled back the
whole activation (asyncpg DataError, order wedged in 'processing').

Revision ID: d19c6a05e3b2
Revises: b7d2e9f1c3a5
Create Date: 2026-07-07 12:45:00
"""
import sqlalchemy as sa
from alembic import op

revision = "d19c6a05e3b2"
down_revision = "b7d2e9f1c3a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("vip_orders", "approved_by", existing_type=sa.Integer(), type_=sa.BigInteger(), existing_nullable=True)
    op.alter_column("cashout_requests", "processed_by", existing_type=sa.Integer(), type_=sa.BigInteger(), existing_nullable=True)


def downgrade() -> None:
    op.alter_column("vip_orders", "approved_by", existing_type=sa.BigInteger(), type_=sa.Integer(), existing_nullable=True)
    op.alter_column("cashout_requests", "processed_by", existing_type=sa.BigInteger(), type_=sa.Integer(), existing_nullable=True)
