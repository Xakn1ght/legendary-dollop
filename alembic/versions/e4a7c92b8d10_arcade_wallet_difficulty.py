"""Per-user arcade difficulty on the wallet (admin-set, rides the loadout).

easy | normal | hard | boss_rush (QA mode: bosses from level 2).

Revision ID: e4a7c92b8d10
Revises: d19c6a05e3b2
Create Date: 2026-07-08 02:45:00
"""
import sqlalchemy as sa
from alembic import op

revision = "e4a7c92b8d10"
down_revision = "d19c6a05e3b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "arcade_wallets",
        sa.Column("difficulty", sa.String(16), server_default="normal", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("arcade_wallets", "difficulty")
