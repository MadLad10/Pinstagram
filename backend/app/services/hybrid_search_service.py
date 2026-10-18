"""Hybrid place search: vector similarity + keyword match + distance.

1. The query is embedded and compared (cosine, pgvector HNSW) against each
   verified place's own text and its published reviews; a place's semantic
   rank is its best match, so "good wifi" can find a cafe whose description
   never says so but whose reviews do.
2. Keyword rank comes from the existing weighted tsvector (OR'ed prefix
   terms), amenity overlap and name trigram similarity.
3. The two rankings are merged with Reciprocal Rank Fusion, which needs no
   score calibration between them, then nudged by soft signals: the query
   naming the place's area or category, and distance from the user.

Filters (category, price, area, radius) are hard constraints applied inside
each candidate query. If the embedding provider is off or fails, search
degrades to keyword ranking rather than erroring.
"""

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import get_embedder
from app.core.config import settings
from app.models.place import Place
from app.schemas.place import PlaceSummary
from app.schemas.search import HybridMatch, HybridPlaceResult, HybridSearchResponse
from app.services.search_service import _escape_like

log = logging.getLogger(__name__)

CANDIDATES = 50
RRF_K = 60
# Vector matches must clear the embedder's absolute similarity floor and be at
# least this fraction as similar as the best match; otherwise every place would
# come back for every query.
SEMANTIC_KEEP_RATIO = 0.7
QUERY_EMBED_TIMEOUT_S = 5.0
AREA_BOOST = 0.15
CATEGORY_BOOST = 0.10
DISTANCE_WEIGHT = 0.2  # share of the score given to proximity when a location is sent
DISTANCE_HALF_KM = 2.0  # proximity score halves at this distance

STOPWORDS = {
    "a", "an", "and", "any", "around", "at", "best", "by", "can", "find", "for",
    "from", "good", "great", "i", "in", "is", "it", "me", "near", "nice", "of",
    "on", "or", "place", "places", "show", "some", "somewhere", "spot", "the",
    "to", "want", "where", "with",
}  # fmt: skip

CATEGORY_WORDS = {
    "cafe": {"cafe", "cafes", "coffee", "tea"},
    "restaurant": {"restaurant", "restaurants", "food", "eat", "lunch", "dinner",
                   "biryani", "kacchi"},
    "hotel": {"hotel", "hotels", "stay", "room"},
    "historical": {"historical", "history", "heritage", "fort", "museum", "mosque",
                   "temple"},
    "scenic": {"scenic", "view", "views", "lake", "park", "garden", "nature"},
    "aesthetic": {"aesthetic", "instagram", "photo", "photos", "architecture"},
}  # fmt: skip


@dataclass
class _Candidate:
    semantic_rank: int | None = None
    keyword_rank: int | None = None
    snippet: str | None = None


def query_terms(q: str) -> list[str]:
    """Content words plus joined pairs, so "outdoor seating" also matches the
    `outdoor_seating` amenity."""
    words = [w for w in re.findall(r"\w+", q.lower()) if w not in STOPWORDS][:12]
    pairs = [f"{a}_{b}" for a, b in zip(words, words[1:], strict=False)]
    return words + pairs


def mentioned_categories(q: str) -> set[str]:
    words = set(re.findall(r"\w+", q.lower()))
    return {cat for cat, vocab in CATEGORY_WORDS.items() if words & vocab}


def rrf(rank: int | None) -> float:
    return 0.0 if rank is None else 1.0 / (RRF_K + rank)


def fused_score(
    c: _Candidate,
    *,
    area_hit: bool,
    category_hit: bool,
    distance_m: float | None,
) -> float:
    # Normalized so a place ranked first in both lists scores 1.0.
    base = (rrf(c.semantic_rank) + rrf(c.keyword_rank)) / (2 * rrf(1))
    base += AREA_BOOST * area_hit + CATEGORY_BOOST * category_hit
    if distance_m is not None:
        proximity = 1.0 / (1.0 + distance_m / 1000 / DISTANCE_HALF_KM)
        base = (1 - DISTANCE_WEIGHT) * base + DISTANCE_WEIGHT * proximity
    return round(base, 4)


def _filters(
    category, price_tier, area, near_lat, near_lng, radius_m
) -> tuple[str, dict]:
    clauses, params = ["p.is_verified"], {}
    if category:
        clauses.append("p.category = CAST(:category AS place_category)")
        params["category"] = category
    if price_tier:
        clauses.append("p.price_tier = CAST(:price_tier AS price_tier)")
        params["price_tier"] = price_tier
    if area:
        clauses.append("p.area ILIKE :area")
        params["area"] = _escape_like(area)
    if near_lat is not None and radius_m:
        clauses.append("ST_DWithin(p.location, CAST(:pt AS geography), :radius)")
        params |= {"pt": f"SRID=4326;POINT({near_lng} {near_lat})", "radius": radius_m}
    return " AND ".join(clauses), params


async def _embed_query(q: str, user_id: uuid.UUID | None) -> list[float] | None:
    if not settings.AI_ENABLED:
        return None
    try:
        return await asyncio.wait_for(
            get_embedder().embed_query(q, purpose="search_query", user_id=user_id),
            timeout=QUERY_EMBED_TIMEOUT_S,
        )
    except Exception as exc:
        log.warning("Query embedding failed, using keyword search: %r", exc)
        return None


async def _semantic(
    db, vector, where, params
) -> list[tuple[uuid.UUID, float, str | None]]:
    """(place_id, best distance, closest review text or None), best first."""
    params = params | {
        "qv": "[" + ",".join(f"{x:.6f}" for x in vector) + "]",
        "model": get_embedder().model,
        "n": CANDIDATES,
    }
    place_rows = await db.execute(
        text(f"""
        SELECT pe.place_id, pe.embedding <=> CAST(:qv AS vector) AS dist
        FROM place_embeddings pe JOIN places p ON p.id = pe.place_id
        WHERE pe.model = :model AND {where}
        ORDER BY dist LIMIT :n
        """),
        params,
    )
    review_rows = await db.execute(
        text(f"""
        SELECT re.place_id, r.body, re.embedding <=> CAST(:qv AS vector) AS dist
        FROM review_embeddings re
        JOIN reviews r ON r.id = re.review_id AND r.status = 'published'
        JOIN places p ON p.id = re.place_id
        WHERE re.model = :model AND {where}
        ORDER BY dist LIMIT :n
        """),
        params,
    )
    best: dict[uuid.UUID, float] = {}
    review: dict[uuid.UUID, tuple[float, str]] = {}  # closest review per place
    for row in place_rows.mappings():
        best[row["place_id"]] = row["dist"]
    for row in review_rows.mappings():
        pid = row["place_id"]
        best[pid] = min(best.get(pid, row["dist"]), row["dist"])
        if pid not in review or row["dist"] < review[pid][0]:
            review[pid] = (row["dist"], row["body"])
    if not best:
        return []
    floor = max(
        get_embedder().min_similarity,
        SEMANTIC_KEEP_RATIO * (1 - min(best.values())),
    )
    results = []
    for pid, dist in sorted(best.items(), key=lambda kv: kv[1]):
        if 1 - dist < floor:
            break
        # Show the closest review whenever it is itself a strong match, even
        # if the place's own text matched slightly better.
        snippet = (
            review[pid][1] if pid in review and 1 - review[pid][0] >= floor else None
        )
        results.append((pid, dist, snippet))
    return results


async def _keyword(db, q, terms, where, params) -> list[uuid.UUID]:
    if not terms:
        return []
    words = [t for t in terms if "_" not in t]
    tsq = " | ".join(f"{w}:*" for w in words)
    rows = await db.execute(
        text(f"""
        SELECT p.id,
               ts_rank(p.search_vector, to_tsquery('simple', :tsq))
               + 0.2 * cardinality(ARRAY(
                   SELECT unnest(p.amenities)
                   INTERSECT SELECT unnest(CAST(:terms AS varchar[]))))
               + similarity(p.name, :q) AS kw
        FROM places p
        WHERE {where}
          AND (p.search_vector @@ to_tsquery('simple', :tsq)
               OR p.amenities && CAST(:terms AS varchar[])
               OR similarity(p.name, :q) > 0.3)
        ORDER BY kw DESC, p.avg_rating DESC
        LIMIT :n
        """),
        params | {"tsq": tsq, "terms": terms, "q": q, "n": CANDIDATES},
    )
    return [r[0] for r in rows]


async def hybrid_search(
    db: AsyncSession,
    q: str,
    *,
    category: str | None = None,
    price_tier: str | None = None,
    area: str | None = None,
    near_lat: float | None = None,
    near_lng: float | None = None,
    radius_m: int | None = None,
    limit: int = 10,
    user_id: uuid.UUID | None = None,
) -> HybridSearchResponse:
    q = q.strip()
    where, params = _filters(category, price_tier, area, near_lat, near_lng, radius_m)

    candidates: dict[uuid.UUID, _Candidate] = {}
    vector = await _embed_query(q, user_id)
    if vector is not None:
        for rank, (pid, _dist, snippet) in enumerate(
            await _semantic(db, vector, where, params), start=1
        ):
            candidates[pid] = _Candidate(semantic_rank=rank, snippet=snippet)
    for rank, pid in enumerate(
        await _keyword(db, q, query_terms(q), where, params), start=1
    ):
        candidates.setdefault(pid, _Candidate()).keyword_rank = rank
    if not candidates:
        return HybridSearchResponse(
            items=[], mode="hybrid" if vector is not None else "keyword"
        )

    columns = [Place]
    has_point = near_lat is not None and near_lng is not None
    if has_point:
        point = func.ST_SetSRID(func.ST_MakePoint(near_lng, near_lat), 4326).cast(
            Place.location.type
        )
        columns.append(func.ST_Distance(Place.location, point).label("distance_m"))
    rows = (
        await db.execute(select(*columns).where(Place.id.in_(list(candidates))))
    ).all()

    q_lower = q.lower()
    categories = mentioned_categories(q)
    items = []
    for row in rows:
        place = row[0]
        c = candidates[place.id]
        distance = row[1] if has_point and row[1] is not None else None
        score = fused_score(
            c,
            area_hit=bool(place.area) and place.area.lower() in q_lower,
            category_hit=place.category in categories,
            distance_m=distance,
        )
        summary = PlaceSummary.model_validate(place)
        items.append(
            HybridPlaceResult(
                **summary.model_dump(exclude={"distance_m"}),
                distance_m=round(distance) if distance is not None else None,
                score=score,
                match=HybridMatch(
                    semantic=c.semantic_rank is not None,
                    keyword=c.keyword_rank is not None,
                    review_snippet=_snippet(c.snippet),
                ),
            )
        )
    items.sort(key=lambda r: (-r.score, -r.avg_rating, str(r.id)))
    return HybridSearchResponse(
        items=items[:limit], mode="hybrid" if vector is not None else "keyword"
    )


def _snippet(body: str | None, max_len: int = 160) -> str | None:
    if not body:
        return None
    body = " ".join(body.split())
    return body if len(body) <= max_len else body[: max_len - 1].rsplit(" ", 1)[0] + "…"
