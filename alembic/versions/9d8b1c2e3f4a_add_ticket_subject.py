"""add ticket subject

Revision ID: 9d8b1c2e3f4a
Revises: 6c2a3c1b9a1e
Create Date: 2026-01-02

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9d8b1c2e3f4a"
down_revision: Union[str, Sequence[str], None] = "6c2a3c1b9a1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column(
            "subject",
            sa.String(length=80),
            nullable=False,
            server_default="",
        ),
    )


def downgrade() -> None:
    op.drop_column("tickets", "subject")

