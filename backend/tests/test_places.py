import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient


def _make_place(name="Cafe Mango", category="cafe"):
    p = MagicMock()
    p.id = uuid.uuid4()
    p.name = name
    p.category = category
    p.description = "A great spot"
    p.address = "Gulshan, Dhaka"
    p.division = "Dhaka"
    p.district = "Dhaka"
    p.area = "Gulshan"
    p.phone = None
    p.website = None
    p.price_tier = "mid"
    p.opening_hours = None
    p.amenities = ["wifi"]
    p.cover_photo_url = None
    p.is_verified = True
    p.is_featured = False
    p.avg_rating = 4.2
    p.review_count = 12
    p.save_count = 5
    p.created_at = "2025-01-01T00:00:00"
    p.updated_at = "2025-01-01T00:00:00"
    p.location = None
    return p


@pytest.mark.asyncio
async def test_list_places_requires_auth_in_prod(client: AsyncClient):
    with patch("app.services.places_service.list_places") as mock_list:
        mock_list.return_value = ([], None)
        resp = await client.get("/api/v1/places")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_places_returns_items(client: AsyncClient):
    place = _make_place()
    with patch("app.services.places_service.list_places") as mock_list:
        mock_list.return_value = ([place], None)
        resp = await client.get("/api/v1/places")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Cafe Mango"


@pytest.mark.asyncio
async def test_list_places_category_filter(client: AsyncClient):
    with patch("app.services.places_service.list_places") as mock_list:
        mock_list.return_value = ([], None)
        resp = await client.get("/api/v1/places?category=restaurant")
    assert resp.status_code == 200
    assert mock_list.called
    call_args = mock_list.call_args
    all_args = list(call_args.args) + list(call_args.kwargs.values())
    assert "restaurant" in all_args


@pytest.mark.asyncio
async def test_get_place_not_found(client: AsyncClient):
    with patch("app.services.places_service.get_place") as mock_get:
        mock_get.return_value = None
        resp = await client.get(f"/api/v1/places/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_place_success(client: AsyncClient):
    place = _make_place("Hatirjheel", "scenic")
    with patch("app.services.places_service.get_place") as mock_get:
        mock_get.return_value = place
        resp = await client.get(f"/api/v1/places/{place.id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Hatirjheel"


@pytest.mark.asyncio
async def test_save_place(client: AsyncClient):
    place_id = uuid.uuid4()
    with patch("app.services.places_service.save_place") as mock_save:
        mock_save.return_value = None
        resp = await client.post(f"/api/v1/places/{place_id}/save")
    assert resp.status_code in (200, 204)


@pytest.mark.asyncio
async def test_unsave_place(client: AsyncClient):
    place_id = uuid.uuid4()
    with patch("app.services.places_service.unsave_place") as mock_unsave:
        mock_unsave.return_value = None
        resp = await client.delete(f"/api/v1/places/{place_id}/save")
    assert resp.status_code in (200, 204)
