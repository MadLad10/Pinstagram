import base64
import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.post import PaginatedPosts, PostRead


def _encode_cursor(score: float, post_id: str) -> str:
    return base64.b64encode(json.dumps({"score": score, "id": post_id}).encode()).decode()


def _decode_cursor(cursor: str) -> tuple[float, str]:
    data = json.loads(base64.b64decode(cursor).decode())
    return data["score"], data["id"]


async def get_feed(
    db: AsyncSession,
    user_id: uuid.UUID,
    cursor: str | None,
    limit: int,
    user_lat: float | None = None,
    user_lng: float | None = None,
) -> PaginatedPosts:
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)

    cursor_score, cursor_id = None, None
    if cursor:
        try:
            cursor_score, cursor_id = _decode_cursor(cursor)
        except Exception:
            pass

    nearby_join = ""
    nearby_filter = ""
    if user_lat is not None and user_lng is not None:
        nearby_join = f"""
        LEFT JOIN places pl_nearby ON pl_nearby.id = p.place_id
        """
        nearby_filter = f"""
        OR (
            p.user_id NOT IN (SELECT followee_id FROM follows WHERE follower_id = '{user_id}')
            AND ST_DWithin(pl_nearby.location, ST_GeogFromText('POINT({user_lng} {user_lat})'), 50000)
            AND p.created_at > '{thirty_days_ago.isoformat()}'
            AND p.status = 'published'
            AND p.user_id NOT IN (SELECT blocked_id FROM blocks WHERE blocker_id = '{user_id}')
            AND p.user_id NOT IN (SELECT blocker_id FROM blocks WHERE blocked_id = '{user_id}')
        )
        """

    query = text(f"""
        SELECT DISTINCT
            p.id,
            p.user_id,
            p.place_id,
            p.media_url,
            p.media_type,
            p.thumbnail_url,
            p.caption,
            p.hashtags,
            p.price_mentioned,
            p.rating,
            p.status,
            p.like_count,
            p.comment_count,
            p.created_at,
            u.id as author_id,
            u.name as author_name,
            u.avatar_url as author_avatar,
            u.is_verified as author_verified,
            pl.id as place_id_val,
            pl.name as place_name,
            pl.category as place_category,
            pl.area as place_area,
            pl.district as place_district,
            pl.avg_rating as place_avg_rating,
            EXISTS(SELECT 1 FROM post_likes WHERE user_id = '{user_id}' AND post_id = p.id) as is_liked,
            EXISTS(SELECT 1 FROM saved_places WHERE user_id = '{user_id}' AND place_id = p.place_id) as is_saved,
            (1.0 / (EXTRACT(EPOCH FROM (NOW() - p.created_at)) / 3600 + 24) * 2
             + p.like_count * 0.1) as score
        FROM posts p
        JOIN users u ON u.id = p.user_id
        JOIN places pl ON pl.id = p.place_id
        WHERE p.status = 'published'
          AND u.deleted_at IS NULL
          AND p.user_id NOT IN (SELECT blocked_id FROM blocks WHERE blocker_id = '{user_id}')
          AND p.user_id NOT IN (SELECT blocker_id FROM blocks WHERE blocked_id = '{user_id}')
          AND (
            (p.user_id IN (SELECT followee_id FROM follows WHERE follower_id = '{user_id}')
             AND p.created_at > '{thirty_days_ago.isoformat()}')
            OR (p.like_count > 0 AND p.created_at > '{seven_days_ago.isoformat()}')
            OR (pl.avg_rating >= 4.0)
            {nearby_filter}
          )
        {"AND (score, p.id::text) < (" + str(cursor_score) + ", '" + cursor_id + "')" if cursor_score is not None else ""}
        ORDER BY score DESC, p.id DESC
        LIMIT {limit + 1}
    """)

    result = await db.execute(query)
    rows = result.mappings().all()

    has_more = len(rows) > limit
    rows = rows[:limit]

    from app.schemas.post import AuthorSnippet, PlaceSnippet
    items = []
    for row in rows:
        items.append(PostRead(
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
            is_liked_by_me=bool(row["is_liked"]),
            is_saved_by_me=bool(row["is_saved"]),
            author=AuthorSnippet(id=row["author_id"], name=row["author_name"], avatar_url=row["author_avatar"], is_verified=row["author_verified"]),
            place=PlaceSnippet(id=row["place_id_val"], name=row["place_name"], category=row["place_category"], area=row["place_area"], district=row["place_district"], avg_rating=float(row["place_avg_rating"])),
            created_at=row["created_at"],
        ))

    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        score = 1.0 / ((datetime.now(timezone.utc) - last["created_at"]).total_seconds() / 3600 + 24) * 2 + last["like_count"] * 0.1
        next_cursor = _encode_cursor(score, str(last["id"]))

    return PaginatedPosts(items=items, next_cursor=next_cursor)


async def get_trending(db: AsyncSession, cursor: str | None, limit: int) -> PaginatedPosts:
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    query = text(f"""
        SELECT p.id, p.user_id, p.place_id, p.media_url, p.media_type, p.thumbnail_url,
               p.caption, p.hashtags, p.price_mentioned, p.rating, p.status,
               p.like_count, p.comment_count, p.created_at,
               u.id as author_id, u.name as author_name, u.avatar_url as author_avatar, u.is_verified as author_verified,
               pl.id as place_id_val, pl.name as place_name, pl.category as place_category,
               pl.area as place_area, pl.district as place_district, pl.avg_rating as place_avg_rating
        FROM posts p
        JOIN users u ON u.id = p.user_id
        JOIN places pl ON pl.id = p.place_id
        WHERE p.status = 'published' AND u.deleted_at IS NULL
          AND p.created_at > '{seven_days_ago.isoformat()}'
        ORDER BY p.like_count DESC, p.created_at DESC
        LIMIT {limit + 1}
    """)
    result = await db.execute(query)
    rows = result.mappings().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    from app.schemas.post import AuthorSnippet, PlaceSnippet
    items = [PostRead(
        id=r["id"], media_url=r["media_url"], media_type=r["media_type"],
        thumbnail_url=r["thumbnail_url"], caption=r["caption"], hashtags=r["hashtags"],
        price_mentioned=r["price_mentioned"], rating=r["rating"], status=r["status"],
        like_count=r["like_count"], comment_count=r["comment_count"],
        author=AuthorSnippet(id=r["author_id"], name=r["author_name"], avatar_url=r["author_avatar"], is_verified=r["author_verified"]),
        place=PlaceSnippet(id=r["place_id_val"], name=r["place_name"], category=r["place_category"], area=r["place_area"], district=r["place_district"], avg_rating=float(r["place_avg_rating"])),
        created_at=r["created_at"],
    ) for r in rows]
    next_cursor = _encode_cursor(0, str(rows[-1]["id"])) if has_more and rows else None
    return PaginatedPosts(items=items, next_cursor=next_cursor)
