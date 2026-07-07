"""add admin_audit_logs table

Immutable trail of admin actions (approve/deny/extend/ban/broadcast/coupon/
SMS arm-disarm), written by app.services.audit.record_audit.

Revision ID: a3e91b7c44d0
Revises: 7c1d44e0aa21
Create Date: 2026-07-06 17:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a3e91b7c44d0'
down_revision: Union[str, Sequence[str], None] = '7c1d44e0aa21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'admin_audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('admin_chat_id', sa.String(length=32), nullable=True),
        sa.Column('admin_name', sa.String(length=120), nullable=True),
        sa.Column('ip', sa.String(length=64), nullable=True),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('target_type', sa.String(length=32), nullable=True),
        sa.Column('target_id', sa.String(length=64), nullable=True),
        sa.Column('summary', sa.String(length=300), nullable=True),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_admin_audit_logs_action', 'admin_audit_logs', ['action'])
    op.create_index('ix_admin_audit_logs_created_at', 'admin_audit_logs', ['created_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_admin_audit_logs_created_at', table_name='admin_audit_logs')
    op.drop_index('ix_admin_audit_logs_action', table_name='admin_audit_logs')
    op.drop_table('admin_audit_logs')
