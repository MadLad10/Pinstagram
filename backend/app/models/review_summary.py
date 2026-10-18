import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReviewSummary(Base):
    """LLM summary of a place's published reviews. Every point cites the
    reviews it came from; uncited or unsupported points are dropped before
    saving (see summary_service.ground)."""

    __tablename__ = "review_summaries"

    place_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("places.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # [{"text": str, "review_ids": [uuid, ...]}]
    pros: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    cons: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    best_for: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # The reviews the model was shown; if one is unpublished, regenerate.
    review_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False
    )
    model: Mapped[str] = mapped_column(String, nullable=False)
    # Points the model produced that failed the grounding check.
    dropped_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
