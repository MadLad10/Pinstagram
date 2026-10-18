import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Changing this needs a migration and a full re-embed.
VECTOR_DIM = 1024


class _EmbeddingColumns:
    model: Mapped[str] = mapped_column(String, nullable=False)
    # sha256 of model + embedded text: unchanged text is never re-embedded.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding = mapped_column(Vector(VECTOR_DIM), nullable=False)
    # The source row's updated_at when it was embedded; a newer updated_at
    # marks the row stale.
    source_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class PlaceEmbedding(Base, _EmbeddingColumns):
    """Name, category, area, amenities and description of a verified place."""

    __tablename__ = "place_embeddings"

    place_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("places.id", ondelete="CASCADE"),
        primary_key=True,
    )


class ReviewEmbedding(Base, _EmbeddingColumns):
    """Body of a published review. Pending and rejected reviews are never
    embedded, so unmoderated text can't influence search."""

    __tablename__ = "review_embeddings"

    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reviews.id", ondelete="CASCADE"),
        primary_key=True,
    )
    place_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("places.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
