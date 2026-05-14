import uuid

from sqlalchemy import Enum, ForeignKey, Integer, SmallInteger, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class Review(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "reviews"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    place_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("places.id", ondelete="CASCADE"), nullable=False, index=True)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    price_paid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("pending", "published", "rejected", name="review_status"),
        default="pending",
        nullable=False,
    )
