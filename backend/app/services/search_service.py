from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def search(db: AsyncSession, q: str, search_type: str, cursor: str | None, limit: int) -> dict:
    if len(q) < 2:
        return {"places": [], "users": [], "hashtags": [], "posts": []}

    results: dict = {}

    if search_type in ("places", "all"):
        place_rows = await db.execute(text(f"""
            SELECT id, name, category, cover_photo_url, avg_rating, price_tier, area, district, is_verified
            FROM places
            WHERE is_verified = true
              AND (name ILIKE :q OR area ILIKE :q OR district ILIKE :q)
            ORDER BY
              CASE WHEN name ILIKE :exact THEN 0
                   WHEN name ILIKE :starts THEN 1
                   ELSE 2 END,
              avg_rating DESC
            LIMIT :limit
        """), {"q": f"%{q}%", "exact": q, "starts": f"{q}%", "limit": 5 if search_type == "all" else limit})
        results["places"] = [dict(r) for r in place_rows.mappings()]

    if search_type in ("users", "all"):
        user_rows = await db.execute(text("""
            SELECT id, name, avatar_url, bio, is_verified
            FROM users
            WHERE deleted_at IS NULL AND name ILIKE :q
            LIMIT :limit
        """), {"q": f"%{q}%", "limit": 3 if search_type == "all" else limit})
        results["users"] = [dict(r) for r in user_rows.mappings()]

    if search_type in ("hashtags", "all"):
        hashtag_rows = await db.execute(text("""
            SELECT DISTINCT unnest(hashtags) as tag
            FROM posts
            WHERE status = 'published'
              AND EXISTS (SELECT 1 FROM unnest(hashtags) h WHERE h ILIKE :q)
            LIMIT :limit
        """), {"q": f"{q}%", "limit": 5 if search_type == "all" else limit})
        results["hashtags"] = [r["tag"] for r in hashtag_rows.mappings()]

    if search_type in ("posts", "all"):
        post_rows = await db.execute(text("""
            SELECT p.id, p.media_url, p.media_type, p.thumbnail_url, p.caption,
                   p.like_count, p.created_at,
                   u.name as author_name, pl.name as place_name
            FROM posts p
            JOIN users u ON u.id = p.user_id
            JOIN places pl ON pl.id = p.place_id
            WHERE p.status = 'published' AND u.deleted_at IS NULL
              AND (p.caption ILIKE :q OR EXISTS (SELECT 1 FROM unnest(p.hashtags) h WHERE h ILIKE :q))
            ORDER BY p.like_count DESC
            LIMIT :limit
        """), {"q": f"%{q}%", "limit": 10 if search_type == "all" else limit})
        results["posts"] = [dict(r) for r in post_rows.mappings()]

    return results
