import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class SummaryPoint(BaseModel):
    text: str
    # The published reviews this point came from.
    review_ids: list[uuid.UUID]


class ReviewSummaryRead(BaseModel):
    # ready: summary available; pending: being generated; not_enough_reviews:
    # fewer than 3 published reviews; disabled: AI features are off.
    status: Literal["ready", "pending", "not_enough_reviews", "disabled"]
    pros: list[SummaryPoint] = []
    cons: list[SummaryPoint] = []
    best_for: list[SummaryPoint] = []
    based_on_reviews: int = 0
    generated_at: datetime | None = None
    model: str | None = None
    # Newer reviews exist; a refreshed summary is being generated.
    stale: bool = False
