import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["hotel", "restaurant", "cafe", "scenic", "historical", "aesthetic"]
PriceTier = Literal["budget", "mid", "luxury"]


class PlaceSummary(BaseModel):
    id: uuid.UUID
    name: str
    category: str
    cover_photo_url: str | None
    avg_rating: float
    price_tier: str | None
    area: str | None
    district: str | None
    is_verified: bool
    lat: float | None = None
    lng: float | None = None
    distance_m: float | None = None

    model_config = {"from_attributes": True}


class PlaceRead(BaseModel):
    id: uuid.UUID
    name: str
    category: str
    description: str | None
    address: str
    division: str | None
    district: str | None
    area: str | None
    lat: float | None = None
    lng: float | None = None
    phone: str | None
    website: str | None
    price_tier: str | None
    opening_hours: dict | None
    amenities: list[str] | None
    cover_photo_url: str | None
    is_verified: bool
    avg_rating: float
    review_count: int
    save_count: int
    is_saved_by_me: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class PlaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: Category
    description: str | None = None
    address: str = Field(min_length=1)
    division: str | None = None
    district: str | None = None
    area: str | None = None
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)
    phone: str | None = None
    website: str | None = None
    price_tier: PriceTier | None = None
    cover_photo_url: str | None = None
    opening_hours: dict | None = None
    amenities: list[str] | None = None


class PlaceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    category: Category | None = None
    description: str | None = None
    address: str | None = None
    division: str | None = None
    district: str | None = None
    area: str | None = None
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)
    phone: str | None = None
    website: str | None = None
    price_tier: PriceTier | None = None
    opening_hours: dict | None = None
    amenities: list[str] | None = None
    cover_photo_url: str | None = None


class PaginatedPlaces(BaseModel):
    items: list[PlaceSummary]
    next_cursor: str | None
