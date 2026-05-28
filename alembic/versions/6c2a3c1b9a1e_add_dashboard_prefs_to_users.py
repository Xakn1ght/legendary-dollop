"""add dashboard prefs to users

Revision ID: 6c2a3c1b9a1e
Revises: 11acd4afb40a
Create Date: 2025-12-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6c2a3c1b9a1e"
down_revision: Union[str, Sequence[str], None] = "11acd4afb40a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "dashboard_prefs",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "dashboard_prefs")

