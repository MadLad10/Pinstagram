import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signup_validates_short_password(unauthed_client: AsyncClient):
    resp = await unauthed_client.post(
        "/api/v1/auth/signup",
        json={"email": "test@example.com", "password": "short", "name": "Test User"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_signup_validates_empty_name(unauthed_client: AsyncClient):
    resp = await unauthed_client.post(
        "/api/v1/auth/signup",
        json={"email": "test@example.com", "password": "validpass123", "name": "   "},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_signup_validates_bad_email(unauthed_client: AsyncClient):
    resp = await unauthed_client.post(
        "/api/v1/auth/signup",
        json={"email": "not-an-email", "password": "validpass123", "name": "Test"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_signup_success(unauthed_client: AsyncClient):
    fake_user = MagicMock()
    fake_user.id = uuid.uuid4()
    fake_user.email = "new@example.com"
    fake_user.name = "New User"
    fake_user.bio = None
    fake_user.avatar_url = None
    fake_user.location = None
    fake_user.role = "user"
    fake_user.email_verified = False
    fake_user.is_private = False
    fake_user.is_verified = False

    with patch("app.services.auth_service.signup") as mock_signup:
        mock_signup.return_value = MagicMock(
            access_token="access.token.here",
            refresh_token="refresh.token.here",
            user=MagicMock(
                id=fake_user.id,
                email=fake_user.email,
                name=fake_user.name,
                bio=None,
                avatar_url=None,
                location=None,
                role="user",
                email_verified=False,
                is_private=False,
                is_verified=False,
                model_dump=lambda: {
                    "id": str(fake_user.id),
                    "email": fake_user.email,
                    "name": fake_user.name,
                },
            ),
        )
        resp = await unauthed_client.post(
            "/api/v1/auth/signup",
            json={"email": "new@example.com", "password": "validpass123", "name": "New User"},
        )

    assert resp.status_code in (200, 201)
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_missing_fields(unauthed_client: AsyncClient):
    resp = await unauthed_client.post("/api/v1/auth/login", json={"email": "test@example.com"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_refresh_missing_token(unauthed_client: AsyncClient):
    resp = await unauthed_client.post("/api/v1/auth/refresh", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_healthz(unauthed_client: AsyncClient):
    resp = await unauthed_client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
