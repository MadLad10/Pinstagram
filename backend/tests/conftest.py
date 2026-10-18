"""Integration-test harness.

Tests run against a real Postgres + PostGIS database (`<db>_test`, created and
migrated on first run) so SQL, geography queries, constraints and full-text
search are exercised for real. Every table is truncated before each test.
Object storage is the only thing stubbed (see `fake_storage`).
"""

import os
import subprocess
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from types import SimpleNamespace

# Must be set before the app (and its settings/engine) is imported.
_base_url = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://app:app@localhost:5432/bdvisual"
)
TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", _base_url.rsplit("/", 1)[0] + "/bdvisual_test"
)
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["AI_ENABLED"] = "true"
os.environ["AI_WORKER_ENABLED"] = "false"
os.environ["LLM_FREE_TIER"] = "true"
# Separate Redis DB so rate-limit tests can flush it freely.
os.environ["REDIS_URL"] = (
    os.environ.get("REDIS_URL", "redis://localhost:6379/0").rsplit("/", 1)[0] + "/15"
)

import asyncpg  # noqa: E402
import pytest  # noqa: E402
from geoalchemy2.elements import WKTElement  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.place import Place  # noqa: E402
from app.models.post import Post  # noqa: E402
from app.models.review import Review  # noqa: E402
from app.models.user import User  # noqa: E402

PASSWORD = "password123"


def _create_and_migrate() -> None:
    import asyncio

    dsn = TEST_DB_URL.replace("+asyncpg", "")
    admin_dsn, db_name = dsn.rsplit("/", 1)

    async def _ensure_db():
        conn = await asyncpg.connect(admin_dsn + "/postgres")
        try:
            exists = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", db_name
            )
            if not exists:
                await conn.execute(f'CREATE DATABASE "{db_name}"')
        finally:
            await conn.close()

    asyncio.run(_ensure_db())
    subprocess.run(
        ["alembic", "upgrade", "head"],
        check=True,
        cwd=os.path.dirname(os.path.dirname(__file__)),
        env=os.environ.copy(),
        capture_output=True,
    )


def pytest_sessionstart(session):
    _create_and_migrate()


@pytest.fixture(autouse=True)
async def _clean_db():
    async with AsyncSessionLocal() as db:
        tables = (
            (
                await db.execute(
                    text(
                        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
                        "AND tablename NOT IN ('alembic_version', 'spatial_ref_sys')"
                    )
                )
            )
            .scalars()
            .all()
        )
        await db.execute(text(f"TRUNCATE {', '.join(tables)} CASCADE"))
        await db.commit()
    yield


@pytest.fixture(autouse=True)
def _fresh_redis_client():
    """The Redis client is bound to the event loop that created it, and each
    test gets a new loop."""
    from app.core import rate_limit

    rate_limit._redis = None
    yield
    rate_limit._redis = None


@pytest.fixture(autouse=True)
def fake_ai():
    """Every test runs against deterministic fakes; nothing reaches a real model.
    Script replies with `fake_ai.llm.queue(...)`."""
    from app import ai
    from app.ai.fake import FakeEmbedder, FakeLLM

    fakes = SimpleNamespace(llm=FakeLLM(), embedder=FakeEmbedder())
    ai.set_providers(llm=fakes.llm, embedder=fakes.embedder)
    yield fakes
    ai.set_providers()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture
def fake_storage(monkeypatch):
    """Pretend every uploaded object exists with the given size."""
    sizes: dict[str, int] = {}

    async def _media_size(file_key: str) -> int:
        from fastapi import HTTPException

        if file_key not in sizes:
            raise HTTPException(status_code=400, detail="File not found in storage")
        return sizes[file_key]

    monkeypatch.setattr("app.services.posts_service._media_size", _media_size)
    return sizes


# ---------------------------------------------------------------- factories


class Actor:
    """A user plus a ready-to-use Authorization header."""

    def __init__(self, user: User):
        self.user = user
        self.id = user.id
        self.headers = {
            "Authorization": f"Bearer {create_access_token(user.id, user.role)}"
        }


@pytest.fixture
def make_user():
    async def _make(
        name: str = "User",
        role: str = "user",
        email: str | None = None,
        **fields,
    ) -> Actor:
        async with AsyncSessionLocal() as db:
            user = User(
                email=email or f"{uuid.uuid4().hex[:10]}@example.com",
                name=name,
                role=role,
                password_hash=hash_password(PASSWORD),
                email_verified=True,
                **fields,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            return Actor(user)

    return _make


@pytest.fixture
def make_place():
    async def _make(
        name: str = "Test Place",
        lat: float | None = 23.7937,
        lng: float | None = 90.4066,
        category: str = "cafe",
        area: str = "Banani",
        verified: bool = True,
        **fields,
    ) -> Place:
        async with AsyncSessionLocal() as db:
            place = Place(
                name=name,
                category=category,
                address=f"{area}, Dhaka",
                area=area,
                district="Dhaka",
                location=WKTElement(f"POINT({lng} {lat})", srid=4326)
                if lat is not None
                else None,
                is_verified=verified,
                **fields,
            )
            db.add(place)
            await db.commit()
            await db.refresh(place)
            return place

    return _make


@pytest.fixture
def make_post():
    async def _make(
        author: Actor,
        place: Place,
        status: str = "published",
        created_at: datetime | None = None,
        **fields,
    ) -> Post:
        async with AsyncSessionLocal() as db:
            created_at = created_at or datetime.now(UTC)
            post = Post(
                user_id=author.id,
                place_id=place.id,
                media_url="https://example.com/p.jpg",
                media_type="image",
                status=status,
                created_at=created_at,
                updated_at=created_at,
                **fields,
            )
            db.add(post)
            await db.commit()
            await db.refresh(post)
            return post

    return _make


@pytest.fixture
def make_review():
    async def _make(
        author: Actor,
        place: Place,
        body: str = "Nice place.",
        rating: int = 4,
        status: str = "published",
        **fields,
    ) -> Review:
        async with AsyncSessionLocal() as db:
            review = Review(
                user_id=author.id,
                place_id=place.id,
                body=body,
                rating=rating,
                status=status,
                **fields,
            )
            db.add(review)
            await db.commit()
            await db.refresh(review)
            return review

    return _make


async def collect_pages(
    client: AsyncClient, url: str, headers=None, **params
) -> list[dict]:
    """Follow next_cursor until exhausted and return every item."""
    items, cursor = [], None
    for _ in range(100):
        resp = await client.get(
            url,
            headers=headers,
            params={**params, "cursor": cursor} if cursor else params,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        items.extend(body["items"])
        cursor = body["next_cursor"]
        if not cursor:
            return items
    raise AssertionError("pagination did not terminate")
