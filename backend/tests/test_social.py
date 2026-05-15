import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_user_profile(client: AsyncClient, user_id: uuid.UUID):
    target_id = uuid.uuid4()
    with patch("app.services.social_service.get_user_profile") as mock_get:
        mock_get.return_value = MagicMock(
            id=target_id,
            name="Other User",
            bio=None,
            avatar_url=None,
            location=None,
            is_private=False,
            is_verified=False,
            role="user",
            follower_count=3,
            following_count=1,
            post_count=7,
            is_following=False,
            is_blocked=False,
        )
        resp = await client.get(f"/api/v1/users/{target_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "follower_count" in data


@pytest.mark.asyncio
async def test_follow_user(client: AsyncClient):
    target_id = uuid.uuid4()
    with patch("app.services.social_service.follow_user") as mock_follow:
        mock_follow.return_value = None
        resp = await client.post(f"/api/v1/users/{target_id}/follow")
    assert resp.status_code == 204
    mock_follow.assert_called_once()


@pytest.mark.asyncio
async def test_unfollow_user(client: AsyncClient):
    target_id = uuid.uuid4()
    with patch("app.services.social_service.unfollow_user") as mock_unfollow:
        mock_unfollow.return_value = None
        resp = await client.delete(f"/api/v1/users/{target_id}/follow")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_block_user(client: AsyncClient):
    target_id = uuid.uuid4()
    with patch("app.services.social_service.block_user") as mock_block:
        mock_block.return_value = None
        resp = await client.post(f"/api/v1/users/{target_id}/block")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_get_saved_places(client: AsyncClient):
    with patch("app.services.social_service.get_saved_places") as mock_saved:
        mock_saved.return_value = ([], None)
        resp = await client.get("/api/v1/users/me/saved-places")
    assert resp.status_code == 200
    assert "items" in resp.json()


@pytest.mark.asyncio
async def test_update_me_patches_user(client: AsyncClient, mock_db: AsyncMock):
    fake_user = MagicMock()
    fake_user.id = uuid.uuid4()
    fake_user.name = "Updated Name"
    fake_user.email = "test@example.com"
    fake_user.bio = "New bio"
    fake_user.avatar_url = None
    fake_user.location = None
    fake_user.role = "user"
    fake_user.email_verified = True
    fake_user.is_private = False
    fake_user.is_verified = False

    mock_result = MagicMock()
    mock_result.scalar_one.return_value = fake_user
    mock_db.execute.return_value = mock_result

    resp = await client.patch("/api/v1/users/me", json={"name": "Updated Name", "bio": "New bio"})
    assert resp.status_code == 200
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_unauthenticated_access_denied(unauthed_client: AsyncClient):
    resp = await unauthed_client.post(f"/api/v1/users/{uuid.uuid4()}/follow")
    assert resp.status_code == 401
