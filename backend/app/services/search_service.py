"""Unified search across places, users, hashtags and posts.

Places use the generated `search_vector` column (GIN-indexed) with prefix
matching, so "cafe ban" finds "Cafe Mango, Banani". A pg_trgm similarity
fallback catches typos ("lalbag" -> "Lalbagh Fort").
"""

import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.places_service import prefix_tsquery


async def search(db: AsyncSession, q: str, search_type: str, limit: int) -> dict:
    q = q.strip()
    results: dict = {}
    tsq = prefix_tsquery(q)
    if not tsq:
        return {"places": [], "users": [], "hashtags": [], "posts": []}
    is_all = search_type == "all"

    if search_type in ("places", "all"):
        rows = await db.execute(
            text("""
            SELECT id, name, category, cover_photo_url, avg_rating, price_tier,
                   area, district, is_verified,
                   ST_Y(location::geometry) AS lat, ST_X(location::geometry) AS lng,
                   ts_rank(search_vector, to_tsquery('simple', :tsq)) AS rank,
                   similarity(name, :q) AS sim
            FROM places
            WHERE is_verified
              AND (search_vector @@ to_tsquery('simple', :tsq) OR similarity(name, :q) > 0.3)
            ORDER BY rank DESC, sim DESC, avg_rating DESC
            LIMIT :limit
            """),
            {"tsq": tsq, "q": q, "limit": 5 if is_all else limit},
        )
        results["places"] = [
            {k: v for k, v in r.items() if k not in ("rank", "sim")}
            | {"avg_rating": float(r["avg_rating"])}
            for r in rows.mappings()
        ]

    if search_type in ("users", "all"):
        rows = await db.execute(
            text("""
            SELECT id, name, avatar_url, bio, is_verified
            FROM users
            WHERE deleted_at IS NULL AND banned_at IS NULL
              AND (name ILIKE :prefix OR similarity(name, :q) > 0.3)
            ORDER BY similarity(name, :q) DESC
            LIMIT :limit
            """),
            {"prefix": f"{_escape_like(q)}%", "q": q, "limit": 3 if is_all else limit},
        )
        results["users"] = [dict(r) for r in rows.mappings()]

    if search_type in ("hashtags", "all"):
        tag = re.sub(r"\W", "", q.lstrip("#").lower())
        rows = await db.execute(
            text("""
            SELECT tag, count(*) AS uses
            FROM posts, unnest(hashtags) AS tag
            WHERE status = 'published' AND tag LIKE :prefix
            GROUP BY tag
            ORDER BY uses DESC
            LIMIT :limit
            """),
            {"prefix": f"{tag}%", "limit": 5 if is_all else limit},
        )
        results["hashtags"] = [r["tag"] for r in rows.mappings()] if tag else []

    if search_type in ("posts", "all"):
        tag = re.sub(r"\W", "", q.lstrip("#").lower())
        rows = await db.execute(
            text("""
            SELECT p.id, p.media_url, p.media_type, p.thumbnail_url, p.caption,
                   p.like_count, p.created_at,
                   u.name AS author_name, pl.id AS place_id, pl.name AS place_name
            FROM posts p
            JOIN users u ON u.id = p.user_id
            JOIN places pl ON pl.id = p.place_id
            WHERE p.status = 'published' AND u.deleted_at IS NULL
              AND (p.search_vector @@ to_tsquery('simple', :tsq) OR p.hashtags @> ARRAY[:tag]::varchar[])
            ORDER BY p.like_count DESC, p.created_at DESC
            LIMIT :limit
            """),
            {"tsq": tsq, "tag": tag, "limit": 10 if is_all else limit},
        )
        results["posts"] = [dict(r) for r in rows.mappings()]

    return results


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
