"""Feed queries.

All three feeds use keyset (cursor) pagination. Cursors are opaque base64 JSON
blobs; every value taken from them is passed to Postgres as a bound parameter.
"""

import base64
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.post import AuthorSnippet, PaginatedPosts, PlaceSnippet, PostRead

_POST_COLUMNS = """
    p.id, p.media_url, p.media_type, p.thumbnail_url, p.caption, p.hashtags,
    p.price_mentioned, p.rating, p.status, p.like_count, p.comment_count, p.created_at,
    u.id AS author_id, u.name AS author_name, u.avatar_url AS author_avatar,
    u.is_verified AS author_verified,
    pl.id AS place_id_val, pl.name AS place_name, pl.category AS place_category,
    pl.area AS place_area, pl.district AS place_district,
    pl.avg_rating AS place_avg_rating
"""

_VIEWER_FLAGS = """
    EXISTS(SELECT 1 FROM post_likes WHERE user_id = :viewer AND post_id = p.id) AS is_liked,
    EXISTS(SELECT 1 FROM saved_places WHERE user_id = :viewer AND place_id = p.place_id) AS is_saved
"""

_NOT_BLOCKED = """
    p.user_id NOT IN (SELECT blocked_id FROM blocks WHERE blocker_id = :viewer)
    AND p.user_id NOT IN (SELECT blocker_id FROM blocks WHERE blocked_id = :viewer)
"""


def _encode_cursor(data: dict[str, Any]) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()


def _decode_cursor(cursor: str) -> dict[str, Any]:
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        if not isinstance(data, dict):
            raise ValueError
        return data
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid cursor") from None


def _row_to_post(row: Any) -> PostRead:
    return PostRead(
        id=row["id"],
        media_url=row["media_url"],
        media_type=row["media_type"],
        thumbnail_url=row["thumbnail_url"],
        caption=row["caption"],
        hashtags=row["hashtags"],
        price_mentioned=row["price_mentioned"],
        rating=row["rating"],
        status=row["status"],
        like_count=row["like_count"],
        comment_count=row["comment_count"],
        is_liked_by_me=bool(row.get("is_liked", False)),
        is_saved_by_me=bool(row.get("is_saved", False)),
        author=AuthorSnippet(
            id=row["author_id"],
            name=row["author_name"],
            avatar_url=row["author_avatar"],
            is_verified=row["author_verified"],
        ),
        place=PlaceSnippet(
            id=row["place_id_val"],
            name=row["place_name"],
            category=row["place_category"],
            area=row["place_area"],
            district=row["place_district"],
            avg_rating=float(row["place_avg_rating"]),
        ),
        created_at=row["created_at"],
    )


async def get_feed(
    db: AsyncSession,
    user_id: uuid.UUID,
    cursor: str | None,
    limit: int,
    user_lat: float | None = None,
    user_lng: float | None = None,
) -> PaginatedPosts:
    """Personalized feed: followed users, recently-liked posts, highly rated
    places and (if a location is given) posts within 50 km.

    Score = recency decay + popularity. The reference time is frozen in the
    cursor so scores stay stable while the user pages through.
    """
    params: dict[str, Any] = {"viewer": user_id, "limit": limit + 1}
    if cursor:
        c = _decode_cursor(cursor)
        try:
            params["ref_time"] = datetime.fromisoformat(c["t"])
            params["cursor_score"] = float(c["s"])
            params["cursor_id"] = uuid.UUID(c["id"])
        except (KeyError, ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid cursor") from None
    else:
        params["ref_time"] = datetime.now(UTC)

    params["follow_since"] = params["ref_time"] - timedelta(days=30)
    params["liked_since"] = params["ref_time"] - timedelta(days=7)

    nearby_clause = ""
    if user_lat is not None and user_lng is not None:
        params["lat"], params["lng"] = user_lat, user_lng
        nearby_clause = """
            OR (p.created_at > :follow_since
                AND ST_DWithin(pl.location,
                               ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                               50000))
        """

    cursor_clause = "WHERE (score, id) < (:cursor_score, :cursor_id)" if cursor else ""

    query = text(f"""
        WITH scored AS (
            SELECT {_POST_COLUMNS}, {_VIEWER_FLAGS},
                   (2.0 / (GREATEST(EXTRACT(EPOCH FROM (:ref_time - p.created_at)), 0) / 3600 + 24)
                    + p.like_count * 0.1)::float8 AS score
            FROM posts p
            JOIN users u ON u.id = p.user_id
            JOIN places pl ON pl.id = p.place_id
            WHERE p.status = 'published'
              AND u.deleted_at IS NULL
              AND p.created_at <= :ref_time
              AND {_NOT_BLOCKED}
              AND (
                (p.user_id IN (SELECT followee_id FROM follows WHERE follower_id = :viewer)
                 AND p.created_at > :follow_since)
                OR (p.like_count > 0 AND p.created_at > :liked_since)
                OR pl.avg_rating >= 4.0
                {nearby_clause}
              )
        )
        SELECT * FROM scored
        {cursor_clause}
        ORDER BY score DESC, id DESC
        LIMIT :limit
    """)

    rows = (await db.execute(query, params)).mappings().all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    next_cursor = None
    if has_more:
        last = rows[-1]
        next_cursor = _encode_cursor(
            {
                "t": params["ref_time"].isoformat(),
                "s": last["score"],
                "id": str(last["id"]),
            }
        )
    return PaginatedPosts(
        items=[_row_to_post(r) for r in rows], next_cursor=next_cursor
    )


async def get_trending(
    db: AsyncSession,
    cursor: str | None,
    limit: int,
    viewer_id: uuid.UUID | None = None,
) -> PaginatedPosts:
    """Most-liked published posts from the last 7 days."""
    params: dict[str, Any] = {
        "since": datetime.now(UTC) - timedelta(days=7),
        "limit": limit + 1,
        "viewer": viewer_id,
    }
    cursor_clause = ""
    if cursor:
        c = _decode_cursor(cursor)
        try:
            params["c_likes"] = int(c["l"])
            params["c_created"] = datetime.fromisoformat(c["t"])
            params["c_id"] = uuid.UUID(c["id"])
        except (KeyError, ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid cursor") from None
        cursor_clause = (
            "AND (p.like_count, p.created_at, p.id) < (:c_likes, :c_created, :c_id)"
        )

    viewer_flags = (
        _VIEWER_FLAGS if viewer_id else "false AS is_liked, false AS is_saved"
    )
    query = text(f"""
        SELECT {_POST_COLUMNS}, {viewer_flags}
        FROM posts p
        JOIN users u ON u.id = p.user_id
        JOIN places pl ON pl.id = p.place_id
        WHERE p.status = 'published' AND u.deleted_at IS NULL
          AND p.created_at > :since
          {cursor_clause}
        ORDER BY p.like_count DESC, p.created_at DESC, p.id DESC
        LIMIT :limit
    """)
    rows = (await db.execute(query, params)).mappings().all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    next_cursor = None
    if has_more:
        last = rows[-1]
        next_cursor = _encode_cursor(
            {
                "l": last["like_count"],
                "t": last["created_at"].isoformat(),
                "id": str(last["id"]),
            }
        )
    return PaginatedPosts(
        items=[_row_to_post(r) for r in rows], next_cursor=next_cursor
    )


async def get_nearby(
    db: AsyncSession,
    viewer_id: uuid.UUID,
    lat: float,
    lng: float,
    radius_m: int,
    cursor: str | None,
    limit: int,
) -> PaginatedPosts:
    """Newest published posts at places within `radius_m` of a point."""
    params: dict[str, Any] = {
        "viewer": viewer_id,
        "lat": lat,
        "lng": lng,
        "radius": radius_m,
        "limit": limit + 1,
    }
    cursor_clause = ""
    if cursor:
        c = _decode_cursor(cursor)
        try:
            params["c_created"] = datetime.fromisoformat(c["t"])
            params["c_id"] = uuid.UUID(c["id"])
        except (KeyError, ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid cursor") from None
        cursor_clause = "AND (p.created_at, p.id) < (:c_created, :c_id)"

    query = text(f"""
        SELECT {_POST_COLUMNS}, {_VIEWER_FLAGS}
        FROM posts p
        JOIN users u ON u.id = p.user_id
        JOIN places pl ON pl.id = p.place_id
        WHERE p.status = 'published' AND u.deleted_at IS NULL
          AND {_NOT_BLOCKED}
          AND ST_DWithin(pl.location,
                         ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                         :radius)
          {cursor_clause}
        ORDER BY p.created_at DESC, p.id DESC
        LIMIT :limit
    """)
    rows = (await db.execute(query, params)).mappings().all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    next_cursor = None
    if has_more:
        last = rows[-1]
        next_cursor = _encode_cursor(
            {"t": last["created_at"].isoformat(), "id": str(last["id"])}
        )
    return PaginatedPosts(
        items=[_row_to_post(r) for r in rows], next_cursor=next_cursor
    )
