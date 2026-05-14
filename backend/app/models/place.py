import uuid

from geoalchemy2 import Geography
from sqlalchemy import ARRAY, Boolean, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class Place(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "places"

    name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(
        Enum("hotel", "restaurant", "cafe", "scenic", "historical", "aesthetic", name="place_category"),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    division: Mapped[str | None] = mapped_column(String, nullable=True)
    district: Mapped[str | None] = mapped_column(String, nullable=True)
    area: Mapped[str | None] = mapped_column(String, nullable=True)
    location = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    website: Mapped[str | None] = mapped_column(String, nullable=True)
    price_tier: Mapped[str | None] = mapped_column(
        Enum("budget", "mid", "luxury", name="price_tier"),
        nullable=True,
    )
    opening_hours: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    amenities: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    cover_photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    avg_rating: Mapped[float] = mapped_column(Numeric(2, 1), default=0.0, nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    save_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
