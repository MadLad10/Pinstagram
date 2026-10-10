import pytest

from app.core import rate_limit
from app.core.config import settings


@pytest.fixture
async def limiter_on(monkeypatch):
    """Enable rate limiting against the real Redis, on a clean slate."""
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    redis = rate_limit.get_redis()
    try:
        await redis.ping()
    except Exception:
        pytest.skip("Redis not available")
    await redis.flushdb()
    yield
    await redis.flushdb()
    await rate_limit.close_redis()


async def test_auth_endpoints_limited_per_ip(client, limiter_on):
    body = {"email": "x@example.com", "password": "whatever123"}
    codes = [
        (await client.post("/api/v1/auth/login", json=body)).status_code
        for _ in range(11)
    ]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429

    resp = await client.post("/api/v1/auth/login", json=body)
    assert resp.status_code == 429
    assert 0 < int(resp.headers["Retry-After"]) <= 60


async def test_verify_email_attempts_capped_per_account(client, limiter_on):
    body = {"email": "x@example.com", "code": "123456"}
    codes = [
        (await client.post("/api/v1/auth/verify-email", json=body)).status_code
        for _ in range(6)
    ]
    assert codes[:5] == [400] * 5
    assert codes[5] == 429


async def test_limiter_fails_open_without_redis(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "REDIS_URL", "redis://127.0.0.1:1/0")
    await rate_limit.close_redis()
    try:
        assert (await client.get("/healthz")).status_code == 200
        resp = await client.get("/api/v1/places")
        assert resp.status_code == 200
    finally:
        await rate_limit.close_redis()
