"""Initial schema — generation_records table

Версионирование данных — первая миграция, создаёт таблицу истории генераций.

Revision ID: 001
Revises:
Create Date: 2026-06-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Версионирование данных — создаём основную таблицу
    op.create_table(
        "generation_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("task_id", sa.String(64), nullable=False, unique=True),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("result", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("max_tokens", sa.Integer, nullable=False, server_default="256"),
        sa.Column("creativity", sa.Float, nullable=False, server_default="0.7"),
        sa.Column("inference_time", sa.Float, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_generation_records_task_id", "generation_records", ["task_id"])
    op.create_index("ix_generation_records_status", "generation_records", ["status"])
    op.create_index("ix_generation_records_created_at", "generation_records", ["created_at"])


def downgrade() -> None:
    op.drop_table("generation_records")
