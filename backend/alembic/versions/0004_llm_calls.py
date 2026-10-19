"""llm_calls: one row per model request (tokens, latency, cost)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-18
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_calls",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("purpose", sa.String, nullable=False),
        sa.Column("provider", sa.String, nullable=False),
        sa.Column("model", sa.String, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "tokens_estimated", sa.Boolean, nullable=False, server_default="false"
        ),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column(
            "list_cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"
        ),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_llm_calls_created", "llm_calls", ["created_at"])
    # Per-user daily budgets for the assistant.
    op.create_index("ix_llm_calls_user_created", "llm_calls", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("llm_calls")
