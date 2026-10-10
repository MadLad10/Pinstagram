import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    body: str = Field(min_length=50, max_length=2000)
    price_paid: int | None = Field(None, ge=0)


class ReviewUpdate(BaseModel):
    rating: int | None = Field(None, ge=1, le=5)
    body: str | None = Field(None, min_length=50, max_length=2000)
    price_paid: int | None = Field(None, ge=0)


class ReviewRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    place_id: uuid.UUID
    rating: int
    body: str
    price_paid: int | None
    status: str
    created_at: datetime
    updated_at: datetime
    author_name: str | None = None
    author_avatar_url: str | None = None

    model_config = {"from_attributes": True}


class PaginatedReviews(BaseModel):
    items: list[ReviewRead]
    next_cursor: str | None
