import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class ReviewCreate(BaseModel):
    rating: int
    body: str
    price_paid: int | None = None

    @field_validator("rating")
    @classmethod
    def rating_range(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError("Rating must be between 1 and 5")
        return v

    @field_validator("body")
    @classmethod
    def body_length(cls, v: str) -> str:
        if len(v) < 50:
            raise ValueError("Review body must be at least 50 characters")
        if len(v) > 2000:
            raise ValueError("Review body must not exceed 2000 characters")
        return v


class ReviewUpdate(BaseModel):
    rating: int | None = None
    body: str | None = None
    price_paid: int | None = None


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
