import uuid

from geoalchemy2 import Geography
from sqlalchemy import ARRAY, Enum, ForeignKey, Integer, String, Text, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class BusStop(Base, UUIDMixin):
    __tablename__ = "bus_stops"

    name: Mapped[str] = mapped_column(String, nullable=False)
    location = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    division: Mapped[str | None] = mapped_column(String, nullable=True)
    district: Mapped[str | None] = mapped_column(String, nullable=True)


class BusRoute(Base, UUIDMixin):
    __tablename__ = "bus_routes"

    name: Mapped[str] = mapped_column(String, nullable=False)
    operator: Mapped[str | None] = mapped_column(String, nullable=True)
    stops: Mapped[list[str]] = mapped_column(ARRAY(UUID(as_uuid=False)), nullable=False)
    typical_fare: Mapped[int] = mapped_column(Integer, nullable=False)
    typical_duration_min: Mapped[int] = mapped_column(Integer, nullable=False)


class TrainStation(Base, UUIDMixin):
    __tablename__ = "train_stations"

    name: Mapped[str] = mapped_column(String, nullable=False)
    location = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    division: Mapped[str | None] = mapped_column(String, nullable=True)


class TrainSchedule(Base, UUIDMixin):
    __tablename__ = "train_schedules"

    from_station_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("train_stations.id"), nullable=False)
    to_station_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("train_stations.id"), nullable=False)
    departure_time = mapped_column(Time, nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    fare: Mapped[int] = mapped_column(Integer, nullable=False)
    days_of_week: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False)


class TransportFare(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "transport_fares"

    provider: Mapped[str] = mapped_column(
        Enum("uber", "pathao", "obhai", name="ridehail_provider"), nullable=False
    )
    base_fare: Mapped[int] = mapped_column(Integer, nullable=False)
    per_km: Mapped[int] = mapped_column(Integer, nullable=False)
    per_min: Mapped[int] = mapped_column(Integer, nullable=False)
