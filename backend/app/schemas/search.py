from typing import Literal

from pydantic import BaseModel

from app.schemas.place import PlaceSummary


class HybridMatch(BaseModel):
    """Why a place matched, so the UI (and the assistant) can explain it."""

    semantic: bool
    keyword: bool
    # Closest published review to the query, when it is itself a strong match.
    review_snippet: str | None = None


class HybridPlaceResult(PlaceSummary):
    score: float
    match: HybridMatch


class HybridSearchResponse(BaseModel):
    items: list[HybridPlaceResult]
    # "keyword" when embeddings are disabled or the provider is unavailable.
    mode: Literal["hybrid", "keyword"]
