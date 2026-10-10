import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from app.db.session import AsyncSessionLocal
from app.models.user import User
from tests.conftest import collect_pages


def _new_key() -> str:
    return f"uploads/{uuid.uuid4()}.jpg"


@pytest.fixture
async def world(make_user, make_place):
    """An author, a viewer and an admin around one place."""
    return {
        "author": await make_user("Author"),
        "viewer": await make_user("Viewer"),
        "admin": await make_user("Admin", role="admin"),
        "place": await make_place("Cafe Mango", avg_rating=4.5),
    }


async def _create_post(client, fake_storage, actor, place, **extra):
    key = _new_key()
    fake_storage[key] = 1024
    return await client.post(
        "/api/v1/posts",
        headers=actor.headers,
        json={
            "place_id": str(place.id),
            "file_key": key,
            "media_type": "image",
            **extra,
        },
    )


async def test_post_moderation_loop(client, fake_storage, world):
    author, viewer, admin, place = (
        world["author"],
        world["viewer"],
        world["admin"],
        world["place"],
    )
    resp = await _create_post(
        client,
        fake_storage,
        author,
        place,
        caption="Hi",
        hashtags=["#Coffee", "coffee", " Dhaka "],
    )
    assert resp.status_code == 201, resp.text
    post = resp.json()
    assert post["status"] == "pending"
    assert post["hashtags"] == ["coffee", "dhaka"]  # normalized + deduped

    # Pending posts are invisible to others and absent from feeds.
    assert (
        await client.get(f"/api/v1/posts/{post['id']}", headers=viewer.headers)
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/posts/{post['id']}", headers=author.headers)
    ).status_code == 200
    feed = (await client.get("/api/v1/feed", headers=viewer.headers)).json()
    assert feed["items"] == []

    # Only admins can approve.
    approve = f"/api/v1/admin/posts/{post['id']}/approve"
    assert (await client.post(approve, headers=author.headers)).status_code == 403
    assert (await client.post(approve, headers=admin.headers)).status_code == 204

    feed = (await client.get("/api/v1/feed", headers=viewer.headers)).json()
    assert [p["id"] for p in feed["items"]] == [post["id"]]

    notes = (await client.get("/api/v1/notifications", headers=author.headers)).json()
    assert notes["unread_count"] == 1 and notes["items"][0]["type"] == "post_approved"


async def test_create_post_validation(client, fake_storage, world, make_place):
    author = world["author"]
    hidden = await make_place("Unverified", verified=False)
    assert (await _create_post(client, fake_storage, author, hidden)).status_code == 404

    bad_key = await client.post(
        "/api/v1/posts",
        headers=author.headers,
        json={
            "place_id": str(world["place"].id),
            "file_key": "../../etc/passwd",
            "media_type": "image",
        },
    )
    assert bad_key.status_code == 422

    missing = await client.post(
        "/api/v1/posts",
        headers=author.headers,
        json={
            "place_id": str(world["place"].id),
            "file_key": _new_key(),
            "media_type": "image",
        },
    )
    assert missing.status_code == 400  # never uploaded

    assert (
        await _create_post(client, fake_storage, author, world["place"], rating=6)
    ).status_code == 422


async def test_oversized_upload_rejected(client, fake_storage, world):
    key = _new_key()
    fake_storage[key] = 51 * 1024 * 1024
    resp = await client.post(
        "/api/v1/posts",
        headers=world["author"].headers,
        json={
            "place_id": str(world["place"].id),
            "file_key": key,
            "media_type": "image",
        },
    )
    assert resp.status_code == 400


async def test_free_users_limited_to_five_posts_per_day(client, fake_storage, world):
    author, place = world["author"], world["place"]
    for _ in range(5):
        assert (
            await _create_post(client, fake_storage, author, place)
        ).status_code == 201
    assert (await _create_post(client, fake_storage, author, place)).status_code == 429

    async with AsyncSessionLocal() as db:
        await db.execute(
            update(User).where(User.id == author.id).values(is_premium=True)
        )
        await db.commit()
    assert (await _create_post(client, fake_storage, author, place)).status_code == 201


async def test_like_is_idempotent_and_notifies(client, world, make_post):
    post = await make_post(world["author"], world["place"])
    url = f"/api/v1/posts/{post.id}/like"
    viewer = world["viewer"]
    for _ in range(3):
        assert (await client.post(url, headers=viewer.headers)).status_code == 204
    got = (await client.get(f"/api/v1/posts/{post.id}", headers=viewer.headers)).json()
    assert got["like_count"] == 1 and got["is_liked_by_me"] is True

    for _ in range(2):
        assert (await client.delete(url, headers=viewer.headers)).status_code == 204
    got = (await client.get(f"/api/v1/posts/{post.id}", headers=viewer.headers)).json()
    assert got["like_count"] == 0

    notes = (
        await client.get("/api/v1/notifications", headers=world["author"].headers)
    ).json()
    assert [n["type"] for n in notes["items"]] == ["like"]
    assert notes["items"][0]["actor"]["name"] == "Viewer"


async def test_cannot_like_pending_or_missing_post(client, world, make_post):
    pending = await make_post(world["author"], world["place"], status="pending")
    viewer = world["viewer"]
    assert (
        await client.post(f"/api/v1/posts/{pending.id}/like", headers=viewer.headers)
    ).status_code == 404
    missing = f"/api/v1/posts/{uuid.uuid4()}/like"
    assert (await client.post(missing, headers=viewer.headers)).status_code == 404


async def test_comments_thread(client, world, make_post):
    author, viewer = world["author"], world["viewer"]
    post = await make_post(author, world["place"])
    url = f"/api/v1/posts/{post.id}/comments"

    assert (
        await client.post(url, headers=viewer.headers, json={"body": "   "})
    ).status_code == 422
    ids = []
    for i in range(7):
        resp = await client.post(url, headers=viewer.headers, json={"body": f"c{i}"})
        assert resp.status_code == 201
        ids.append(resp.json()["id"])

    items = await collect_pages(client, url, limit=3)
    assert [c["body"] for c in items] == [f"c{i}" for i in range(7)]  # oldest first
    assert items[0]["author"]["name"] == "Viewer"

    stranger = world["admin"]  # any other user
    del_url = f"{url}/{ids[0]}"
    assert (await client.delete(del_url, headers=stranger.headers)).status_code == 403
    # The post's author may moderate comments on their own post.
    assert (await client.delete(del_url, headers=author.headers)).status_code == 204
    got = (await client.get(f"/api/v1/posts/{post.id}")).json()
    assert got["comment_count"] == 6


async def test_feed_excludes_blocked_users(client, world, make_post):
    author, viewer = world["author"], world["viewer"]
    authors_post = await make_post(author, world["place"])
    viewers_post = await make_post(viewer, world["place"])

    async def feed_ids(actor):
        resp = await client.get("/api/v1/feed", headers=actor.headers)
        return {p["id"] for p in resp.json()["items"]}

    assert await feed_ids(viewer) == {str(authors_post.id), str(viewers_post.id)}

    await client.post(f"/api/v1/users/{author.id}/block", headers=viewer.headers)
    assert await feed_ids(viewer) == {str(viewers_post.id)}
    # Blocking works in both directions: the blocked user stops seeing the blocker.
    assert await feed_ids(author) == {str(authors_post.id)}


async def test_feed_pagination_is_stable(client, world, make_post):
    now = datetime.now(UTC)
    for i in range(12):
        await make_post(
            world["author"],
            world["place"],
            created_at=now - timedelta(hours=i),
            like_count=i % 3,
        )
    items = await collect_pages(
        client, "/api/v1/feed", headers=world["viewer"].headers, limit=5
    )
    assert len(items) == 12
    assert len({p["id"] for p in items}) == 12


async def test_feed_rejects_tampered_cursor(client, world):
    import base64

    evil = base64.urlsafe_b64encode(
        b'{"t":"2024-01-01T00:00:00","s":1,"id":"x\'; DROP TABLE posts;--"}'
    ).decode()
    resp = await client.get(
        f"/api/v1/feed?cursor={evil}", headers=world["viewer"].headers
    )
    assert resp.status_code == 400


async def test_trending_pagination(client, world, make_post):
    for likes in [5, 3, 3, 3, 1, 0]:
        await make_post(world["author"], world["place"], like_count=likes)
    items = await collect_pages(client, "/api/v1/feed/trending", limit=2)
    assert [p["like_count"] for p in items] == [5, 3, 3, 3, 1, 0]
    assert len({p["id"] for p in items}) == 6


async def test_nearby_feed_respects_radius(client, world, make_place, make_post):
    far = await make_place("Far away", lat=22.3569, lng=91.7832)  # Chittagong
    await make_post(world["author"], world["place"])
    await make_post(world["author"], far)
    resp = await client.get(
        "/api/v1/feed/nearby",
        params={"lat": 23.7937, "lng": 90.4066, "radius_m": 10000},
        headers=world["viewer"].headers,
    )
    assert [p["place"]["name"] for p in resp.json()["items"]] == ["Cafe Mango"]


async def test_user_posts_grid(client, world, make_post):
    author, viewer = world["author"], world["viewer"]
    await make_post(author, world["place"])
    await make_post(author, world["place"], status="pending")
    others = (
        await client.get(f"/api/v1/users/{author.id}/posts", headers=viewer.headers)
    ).json()
    own = (
        await client.get(f"/api/v1/users/{author.id}/posts", headers=author.headers)
    ).json()
    assert len(others["items"]) == 1
    assert len(own["items"]) == 2


async def test_delete_post_only_by_owner(client, world, make_post):
    post = await make_post(world["author"], world["place"])
    url = f"/api/v1/posts/{post.id}"
    assert (
        await client.delete(url, headers=world["viewer"].headers)
    ).status_code == 403
    assert (
        await client.delete(url, headers=world["author"].headers)
    ).status_code == 204
    assert (await client.get(url)).status_code == 404


async def test_presign_rejects_bad_types(client, world):
    resp = await client.post(
        "/api/v1/uploads/presign",
        headers=world["author"].headers,
        json={
            "filename": "x.exe",
            "content_type": "application/x-msdownload",
            "size": 10,
        },
    )
    assert resp.status_code == 400
