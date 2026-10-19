"""review_summaries: cached, citation-checked LLM summaries per place

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-18
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_summaries",
        sa.Column(
            "place_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("places.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("pros", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("cons", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("best_for", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column(
            "review_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
        ),
        sa.Column("model", sa.String, nullable=False),
        sa.Column("dropped_points", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("review_summaries")
