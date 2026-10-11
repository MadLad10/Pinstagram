"""Settings and guards that only matter once the API is publicly hosted."""

import pytest
from starlette.requests import Request

from app.core import rate_limit
from app.core.config import normalize_database_url, settings


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        (
            "postgres://u:p@ep-x.neon.tech/db?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://u:p@ep-x.neon.tech/db?ssl=require",
        ),
        ("postgresql://u:p@host:5432/db", "postgresql+asyncpg://u:p@host:5432/db"),
        (
            "postgresql+asyncpg://app:app@localhost:5432/bdvisual",
            "postgresql+asyncpg://app:app@localhost:5432/bdvisual",
        ),
    ],
)
def test_database_url_normalized_for_asyncpg(given, expected):
    assert normalize_database_url(given) == expected


def _request(xff: str | None, peer: str = "10.0.0.1") -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


def test_client_ip_ignores_forwarded_header_without_trusted_proxy(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 0)
    assert rate_limit.client_ip(_request("6.6.6.6")) == "10.0.0.1"


def test_client_ip_cannot_be_spoofed_behind_proxy(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    # The client sent "6.6.6.6"; the proxy appended the real address.
    assert rate_limit.client_ip(_request("6.6.6.6, 203.0.113.9")) == "203.0.113.9"
    assert rate_limit.client_ip(_request(None)) == "10.0.0.1"


async def test_demo_account_cannot_be_deleted_or_renamed(client, make_user):
    demo = await make_user("Demo", email=settings.DEMO_USER_EMAIL)
    assert (
        await client.delete("/api/v1/users/me", headers=demo.headers)
    ).status_code == 403
    patch = await client.patch(
        "/api/v1/users/me", headers=demo.headers, json={"name": "pwned"}
    )
    assert patch.status_code == 403
    # Normal interactions still work for the demo account.
    other = await make_user("Other")
    assert (
        await client.post(f"/api/v1/users/{other.id}/follow", headers=demo.headers)
    ).status_code == 204


def test_media_url_defaults_and_override(monkeypatch):
    monkeypatch.setattr(settings, "MEDIA_BASE_URL", "")
    monkeypatch.setattr(settings, "S3_PUBLIC_URL", "http://localhost:9000")
    assert settings.media_base_url == f"http://localhost:9000/{settings.S3_BUCKET}"
    monkeypatch.setattr(settings, "MEDIA_BASE_URL", "https://pub-123.r2.dev/")
    assert settings.media_base_url == "https://pub-123.r2.dev"


async def test_uploads_can_be_disabled(client, make_user, monkeypatch):
    monkeypatch.setattr(settings, "UPLOADS_ENABLED", False)
    me = await make_user()
    resp = await client.post(
        "/api/v1/uploads/presign",
        headers=me.headers,
        json={"filename": "a.jpg", "content_type": "image/jpeg", "size": 10},
    )
    assert resp.status_code == 503
    assert "aren't enabled" in resp.json()["detail"]
