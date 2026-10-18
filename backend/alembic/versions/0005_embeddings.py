"""pgvector embeddings for places and published reviews

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-18
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

DIM = 768


def _common_columns() -> list[sa.Column]:
    return [
        sa.Column("model", sa.String, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(DIM), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "place_embeddings",
        sa.Column(
            "place_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("places.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        *_common_columns(),
    )
    op.create_table(
        "review_embeddings",
        sa.Column(
            "review_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reviews.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "place_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("places.id", ondelete="CASCADE"),
            nullable=False,
        ),
        *_common_columns(),
    )
    op.create_index("ix_review_embeddings_place_id", "review_embeddings", ["place_id"])
    # Approximate nearest-neighbour indexes for cosine distance (<=>).
    for table in ("place_embeddings", "review_embeddings"):
        op.execute(
            f"CREATE INDEX ix_{table}_hnsw ON {table} "
            "USING hnsw (embedding vector_cosine_ops)"
        )


def downgrade() -> None:
    op.drop_table("review_embeddings")
    op.drop_table("place_embeddings")
    op.execute("DROP EXTENSION IF EXISTS vector")
