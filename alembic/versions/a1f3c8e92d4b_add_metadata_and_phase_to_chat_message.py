"""Add metadata_json and phase to chat_message.

Revision ID: a1f3c8e92d4b
Revises: b25d38b0cd7c
Create Date: 2026-05-20 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "a1f3c8e92d4b"
down_revision: Union[str, Sequence[str]] = "b25d38b0cd7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    columns = {c["name"] for c in inspect(conn).get_columns("chat_message")}
    if "metadata_json" not in columns:
        op.add_column("chat_message", sa.Column("metadata_json", sa.Text(), nullable=True))
    if "phase" not in columns:
        op.add_column("chat_message", sa.Column("phase", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_message", "phase")
    op.drop_column("chat_message", "metadata_json")
