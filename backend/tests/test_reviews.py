import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


def _make_review(rating=4, body="x" * 60):
    r = MagicMock()
    r.id = uuid.uuid4()
    r.user_id = uuid.uuid4()
    r.place_id = uuid.uuid4()
    r.rating = rating
    r.body = body
    r.price_paid = None
    r.status = "pending"
    r.created_at = "2025-01-01T00:00:00"
    r.updated_at = "2025-01-01T00:00:00"
    r.author_name = "Test User"
    r.author_avatar_url = None
    return r


@pytest.mark.asyncio
async def test_create_review_success(client: AsyncClient):
    place_id = uuid.uuid4()
    review = _make_review()
    with patch("app.services.reviews_service.create_review") as mock_create:
        mock_create.return_value = review
        resp = await client.post(
            f"/api/v1/places/{place_id}/reviews",
            json={"rating": 4, "body": "A" * 60, "price_paid": 500},
        )
    assert resp.status_code in (200, 201)


@pytest.mark.asyncio
async def test_create_review_validates_rating_range(client: AsyncClient):
    place_id = uuid.uuid4()
    resp = await client.post(
        f"/api/v1/places/{place_id}/reviews",
        json={"rating": 6, "body": "A" * 60},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_review_validates_rating_zero(client: AsyncClient):
    place_id = uuid.uuid4()
    resp = await client.post(
        f"/api/v1/places/{place_id}/reviews",
        json={"rating": 0, "body": "A" * 60},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_review_validates_body_length(client: AsyncClient):
    place_id = uuid.uuid4()
    resp = await client.post(
        f"/api/v1/places/{place_id}/reviews",
        json={"rating": 4, "body": "too short"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_reviews(client: AsyncClient):
    place_id = uuid.uuid4()
    review = _make_review()
    with patch("app.services.reviews_service.list_reviews") as mock_list:
        mock_list.return_value = ([review], None)
        resp = await client.get(f"/api/v1/places/{place_id}/reviews")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


@pytest.mark.asyncio
async def test_delete_own_review(client: AsyncClient, user_id: uuid.UUID):
    review_id = uuid.uuid4()
    with patch("app.services.reviews_service.delete_review") as mock_del:
        mock_del.return_value = None
        resp = await client.delete(f"/api/v1/reviews/{review_id}")
    assert resp.status_code in (200, 204)
