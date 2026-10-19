"""Hybrid search and the embedding indexer, against real Postgres + pgvector.

The fake embedder is a hashed bag of words, so "semantic" similarity here is
word overlap; that's enough to verify retrieval plumbing, fusion, filters,
moderation rules and fallbacks deterministically.
"""

import pytest
from sqlalchemy import func, select, update

from app.ai.indexing import embed_all, embed_pending, place_document
from app.ai.types import LLMError
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.embedding import PlaceEmbedding, ReviewEmbedding
from app.models.llm_call import LLMCall
from app.models.place import Place
from app.models.review import Review
from app.services.hybrid_search_service import (
    _Candidate,
    fused_score,
    mentioned_categories,
    query_terms,
)

DHANMONDI = (23.7465, 90.3760)
GULSHAN = (23.7925, 90.4078)


async def _index() -> int:
    async with AsyncSessionLocal() as db:
        return await embed_all(db)


async def _search(client, q, **params):
    resp = await client.get("/api/v1/search/hybrid", params={"q": q, **params})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _names(body) -> list[str]:
    return [p["name"] for p in body["items"]]


@pytest.fixture
async def cafes(make_place, make_user, make_review):
    author = await make_user("Reviewer")
    places = {
        "rooftop_dhanmondi": await make_place(
            "Skyline Terrace",
            category="cafe",
            area="Dhanmondi",
            lat=DHANMONDI[0],
            lng=DHANMONDI[1],
            price_tier="mid",
            amenities=["wifi", "outdoor_seating"],
            description="Rooftop cafe above Satmasjid Road with plants and sunset light.",
        ),
        "rooftop_gulshan": await make_place(
            "Lakeview Rooftop",
            category="cafe",
            area="Gulshan",
            lat=GULSHAN[0],
            lng=GULSHAN[1],
            price_tier="luxury",
            description="Rooftop lounge over Gulshan Lake with mocktails and loud music.",
        ),
        "plain_dhanmondi": await make_place(
            "Corner Bakery",
            category="cafe",
            area="Dhanmondi",
            lat=DHANMONDI[0] + 0.002,
            lng=DHANMONDI[1],
            price_tier="budget",
            description="Fresh buns and milk tea by the roadside.",
        ),
        "biryani": await make_place(
            "Kacchi Ghor",
            category="restaurant",
            area="Dhanmondi",
            lat=DHANMONDI[0] - 0.003,
            lng=DHANMONDI[1],
            price_tier="mid",
            description="Slow-cooked mutton kacchi biryani from giant handi pots.",
        ),
        "moonlight": await make_place(
            "Moonlight Bistro",
            category="cafe",
            area="Banani",
            description="Small menu of sandwiches and cold coffee.",
        ),
    }
    await make_review(
        author,
        places["moonlight"],
        "Very quiet in the mornings, fast wifi and plenty of sockets. Perfect for working on a laptop.",
    )
    await make_review(
        author,
        places["rooftop_dhanmondi"],
        "Quiet and calm up on the roof, the wifi is reliable.",
    )
    return places


async def test_example_query_ranks_the_quiet_dhanmondi_rooftop_first(client, cafes):
    await _index()
    body = await _search(client, "quiet rooftop cafe in Dhanmondi with good wifi")
    assert body["mode"] == "hybrid"
    names = _names(body)
    assert names[0] == "Skyline Terrace"
    # The other rooftop and the other Dhanmondi cafe are relevant, just less so.
    assert {"Lakeview Rooftop", "Corner Bakery"} <= set(names)
    top = body["items"][0]
    assert top["match"] == {
        "semantic": True,
        "keyword": True,
        "review_snippet": "Quiet and calm up on the roof, the wifi is reliable.",
    }


async def test_review_text_makes_a_place_findable(client, cafes):
    """Nothing in Moonlight Bistro's own listing mentions wifi or work; its
    review does."""
    await _index()
    body = await _search(client, "fast wifi for working on a laptop")
    moonlight = next(i for i in body["items"] if i["name"] == "Moonlight Bistro")
    assert moonlight["match"]["semantic"] and not moonlight["match"]["keyword"]
    assert "laptop" in moonlight["match"]["review_snippet"]
    # Keyword search alone can't see review text.
    keyword = await client.get(
        "/api/v1/search", params={"q": "laptop", "type": "places"}
    )
    assert keyword.json()["places"] == []


async def test_unmoderated_reviews_never_influence_search(
    client, make_place, make_user, make_review
):
    author = await make_user()
    place = await make_place("Plain Cafe", description="Tea and snacks.")
    review = await make_review(
        author, place, "Secret zanzibar garden out back.", status="pending"
    )
    await _index()
    assert _names(await _search(client, "zanzibar garden")) == []

    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Review).where(Review.id == review.id).values(status="published")
        )
        await db.commit()
    await _index()
    assert _names(await _search(client, "zanzibar garden")) == ["Plain Cafe"]

    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Review).where(Review.id == review.id).values(status="rejected")
        )
        await db.commit()
    # Excluded immediately by the query, before the indexer runs...
    assert _names(await _search(client, "zanzibar garden")) == []
    # ...and the vector itself is deleted on the next pass.
    await _index()
    async with AsyncSessionLocal() as db:
        assert (await db.scalar(select(func.count()).select_from(ReviewEmbedding))) == 0


async def test_unverified_places_are_not_indexed_or_returned(client, make_place):
    await make_place("Hidden Rooftop", description="Rooftop cafe.", verified=False)
    await _index()
    assert _names(await _search(client, "rooftop cafe")) == []
    async with AsyncSessionLocal() as db:
        assert (await db.scalar(select(func.count()).select_from(PlaceEmbedding))) == 0


async def test_filters_are_hard_constraints(client, cafes):
    await _index()
    q = "rooftop cafe biryani"
    assert _names(await _search(client, q, category="restaurant")) == ["Kacchi Ghor"]
    assert _names(await _search(client, q, price_tier="luxury")) == ["Lakeview Rooftop"]
    assert set(_names(await _search(client, q, area="dhanmondi"))) <= {
        "Skyline Terrace",
        "Corner Bakery",
        "Kacchi Ghor",
    }
    near = await _search(
        client, q, near_lat=GULSHAN[0], near_lng=GULSHAN[1], radius_m=100
    )
    assert _names(near) == ["Lakeview Rooftop"]
    assert near["items"][0]["distance_m"] == 0


async def test_distance_breaks_ties_between_equal_matches(client, make_place):
    for name, lat in [("Far Tea Stall", 23.90), ("Near Tea Stall", 23.7470)]:
        await make_place(
            name, lat=lat, lng=90.3760, description="Milk tea and singara."
        )
    await _index()
    body = await _search(
        client, "milk tea singara", near_lat=DHANMONDI[0], near_lng=DHANMONDI[1]
    )
    assert _names(body) == ["Near Tea Stall", "Far Tea Stall"]
    assert body["items"][0]["distance_m"] < body["items"][1]["distance_m"]


async def test_falls_back_to_keyword_when_embeddings_fail(client, cafes, fake_ai):
    await _index()
    fake_ai.embedder.error = LLMError("provider down")
    body = await _search(client, "rooftop dhanmondi")
    assert body["mode"] == "keyword"
    assert _names(body)[0] == "Skyline Terrace"
    assert not any(item["match"]["semantic"] for item in body["items"])
    async with AsyncSessionLocal() as db:
        statuses = (
            await db.execute(
                select(LLMCall.status).where(LLMCall.purpose == "search_query")
            )
        ).scalars()
        assert list(statuses) == ["error"]


async def test_keyword_only_when_ai_disabled(client, cafes, fake_ai, monkeypatch):
    monkeypatch.setattr(settings, "AI_ENABLED", False)
    body = await _search(client, "rooftop")
    assert body["mode"] == "keyword"
    assert set(_names(body)) == {"Skyline Terrace", "Lakeview Rooftop"}
    assert fake_ai.embedder.calls == []


async def test_query_embeddings_are_cached(client, cafes, fake_ai):
    await _index()
    before = len(fake_ai.embedder.calls)
    await _search(client, "quiet rooftop")
    await _search(client, "  Quiet   ROOFTOP ")
    assert len(fake_ai.embedder.calls) == before + 1


async def test_invalid_location_params(client):
    resp = await client.get(
        "/api/v1/search/hybrid", params={"q": "cafe", "near_lat": 23.7}
    )
    assert resp.status_code == 422
    resp = await client.get(
        "/api/v1/search/hybrid", params={"q": "cafe", "radius_m": 500}
    )
    assert resp.status_code == 422


# ------------------------------------------------------------------ indexer


async def test_indexer_only_reembeds_changed_text(make_place, fake_ai):
    place = await make_place("Cafe Mango", description="Mango cold brew.")
    assert await _index() == 1
    calls = len(fake_ai.embedder.calls)

    # A rating recompute bumps updated_at but not the text: no API call.
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Place).where(Place.id == place.id).values(avg_rating=4.5)
        )
        await db.commit()
    assert await _index() == 1
    assert len(fake_ai.embedder.calls) == calls

    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Place)
            .where(Place.id == place.id)
            .values(description="Now serving rooftop brunch.")
        )
        await db.commit()
    assert await _index() == 1
    assert len(fake_ai.embedder.calls) == calls + 1
    assert "rooftop brunch" in fake_ai.embedder.calls[-1][0]
    async with AsyncSessionLocal() as db:
        assert await embed_pending(db) == 0


async def test_switching_embedding_model_reembeds_everything(
    make_place, make_user, make_review, fake_ai
):
    author = await make_user()
    place = await make_place("A")
    await make_review(author, place, "Lovely.")
    assert await _index() == 2
    fake_ai.embedder.model = "fake-embed-v2"
    assert await _index() == 2
    async with AsyncSessionLocal() as db:
        models = set((await db.execute(select(PlaceEmbedding.model))).scalars())
    assert models == {"fake-embed-v2"}


def test_place_document_includes_searchable_fields():
    doc = place_document(
        {
            "name": "Skyline Terrace",
            "category": "cafe",
            "area": "Dhanmondi",
            "district": "Dhaka",
            "price_tier": "mid",
            "amenities": ["wifi", "outdoor_seating"],
            "description": "Rooftop cafe.",
        }
    )
    assert doc == (
        "Skyline Terrace. cafe in Dhanmondi. Price: mid. "
        "Amenities: wifi, outdoor seating. Rooftop cafe."
    )


# ------------------------------------------------------------------- fusion


def test_query_terms_drop_stopwords_and_join_pairs():
    assert query_terms("a cafe with outdoor seating") == [
        "cafe",
        "outdoor",
        "seating",
        "cafe_outdoor",
        "outdoor_seating",
    ]


def test_mentioned_categories():
    assert mentioned_categories("best biryani near Old Dhaka") == {"restaurant"}
    assert mentioned_categories("coffee and a lake view") == {"cafe", "scenic"}


def test_fused_score_rewards_agreement_and_proximity():
    both = fused_score(
        _Candidate(1, 1), area_hit=False, category_hit=False, distance_m=None
    )
    one = fused_score(
        _Candidate(1, None), area_hit=False, category_hit=False, distance_m=None
    )
    assert both == 1.0 and one == 0.5
    boosted = fused_score(
        _Candidate(1, None), area_hit=True, category_hit=True, distance_m=None
    )
    assert boosted == pytest.approx(0.75)
    near = fused_score(
        _Candidate(2, 2), area_hit=False, category_hit=False, distance_m=100
    )
    far = fused_score(
        _Candidate(2, 2), area_hit=False, category_hit=False, distance_m=20_000
    )
    assert near > far
