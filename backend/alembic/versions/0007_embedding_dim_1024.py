"""embeddings: 768 -> 1024 dimensions (bge-m3, Gemini at 1024)

Embeddings are derived data: rows are cleared and the AI worker (or
`python -m app.scripts.embed_backfill`) rebuilds them.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-18
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

TABLES = ("place_embeddings", "review_embeddings")


def _resize(dim: int) -> None:
    for table in TABLES:
        op.execute(f"DROP INDEX IF EXISTS ix_{table}_hnsw")
        op.execute(f"DELETE FROM {table}")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN embedding TYPE vector({dim})")
        op.execute(
            f"CREATE INDEX ix_{table}_hnsw ON {table} "
            "USING hnsw (embedding vector_cosine_ops)"
        )


def upgrade() -> None:
    _resize(1024)


def downgrade() -> None:
    _resize(768)
