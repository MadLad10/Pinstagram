"""The dev seed: place-specific reviews load, re-running adds nothing, and
--reset-reviews replaces them."""

from sqlalchemy import func, select

from app.db.session import AsyncSessionLocal
from app.models.place import Place
from app.models.review import Review
from app.models.user import User
from app.scripts import seed_dev
from app.scripts.seed_reviews import PLACE_REVIEWS

EXPECTED_REVIEWS = sum(map(len, PLACE_REVIEWS.values()))


async def _count(model, *where) -> int:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(func.count()).select_from(model).where(*where))


async def test_seed_loads_place_specific_reviews_idempotently(monkeypatch):
    monkeypatch.setattr(seed_dev, "ensure_bucket_exists", lambda: None)
    assert set(PLACE_REVIEWS) <= {p[0] for p in seed_dev.PLACES}

    await seed_dev.seed()
    assert await _count(Review) == EXPECTED_REVIEWS
    assert await _count(Review, Review.status != "published") == 0
    async with AsyncSessionLocal() as db:
        demo = await db.scalar(select(User).where(User.email == "demo@pinstagram.app"))
        # The demo account keeps every place open for its own review.
        assert (
            await db.scalar(
                select(func.count())
                .select_from(Review)
                .where(Review.user_id == demo.id)
            )
            == 0
        )
        place = await db.scalar(select(Place).where(Place.name == "Paper & Pour"))
        assert place.review_count == len(PLACE_REVIEWS["Paper & Pour"])
        assert float(place.avg_rating) == 4.0

    await seed_dev.seed()
    assert await _count(Review) == EXPECTED_REVIEWS

    await seed_dev.seed(reset_reviews=True)
    assert await _count(Review) == EXPECTED_REVIEWS
