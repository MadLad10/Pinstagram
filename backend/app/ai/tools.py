"""Tools the trip-planning assistant can call. Each wraps an existing service
(hybrid search, place details, review summaries, directions) and returns a
compact, model-friendly dict.

Arguments are validated with Pydantic; the JSON Schema the model sees is
generated from the same models. Places can be referred to by id or by name,
and trip origins by bus stop, area, landmark or "current location", so the
model doesn't need a separate geocoding step.
"""

import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.types import ToolSpec
from app.models.place import Place
from app.schemas.place import Category, PriceTier
from app.services import directions_service, hybrid_search_service, summary_service
from app.services.directions_service import Point


class ToolError(Exception):
    """A failure the model should see and can recover from (bad place name,
    no route, ...)."""


@dataclass
class Location:
    name: str
    kind: str  # bus_stop | place | area | landmark | user | coordinates
    lat: float
    lng: float

    def label(self) -> str:
        return (
            self.name
            if self.kind in ("user", "coordinates")
            else f"{self.name} ({self.kind.replace('_', ' ')})"
        )


@dataclass
class ToolContext:
    user_location: tuple[float, float] | None = None
    # Everything tools returned, for citations and the grounding check.
    places: dict[uuid.UUID, dict] = field(default_factory=dict)
    routes: list[dict] = field(default_factory=list)

    def remember_place(self, place: Place | dict) -> dict:
        get = place.get if isinstance(place, dict) else lambda k: getattr(place, k)
        ref = {
            "id": str(get("id")),
            "name": get("name"),
            "category": get("category"),
            "area": get("area"),
            "avg_rating": float(get("avg_rating") or 0),
        }
        self.places[uuid.UUID(ref["id"])] = ref
        return ref


# Neighbourhood names people use that aren't a single stop or place.
AREA_ALIASES = {
    "old dhaka": ("Old Dhaka", 23.7150, 90.4010),
    "puran dhaka": ("Old Dhaka", 23.7150, 90.4010),
    "motijheel": ("Motijheel", 23.7330, 90.4172),
    "dhanmondi": ("Dhanmondi", 23.7465, 90.3760),
    "gulshan": ("Gulshan", 23.7925, 90.4078),
    "banani": ("Banani", 23.7940, 90.4043),
    "uttara": ("Uttara", 23.8759, 90.3795),
    "mirpur": ("Mirpur", 23.8069, 90.3687),
    "mohammadpur": ("Mohammadpur", 23.7662, 90.3589),
}
_HERE = {
    "here",
    "me",
    "my location",
    "current location",
    "my current location",
    "where i am",
}


def _norm(s: str) -> str:
    return " ".join(re.findall(r"\w+", s.lower()))


async def resolve_location(db: AsyncSession, query: str, ctx: ToolContext) -> Location:
    q = query.strip()
    key = _norm(q)
    if key in _HERE:
        if ctx.user_location is None:
            raise ToolError(
                "The user's current location isn't available. Ask where they are starting from."
            )
        return Location("your current location", "user", *ctx.user_location)
    if m := re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*", q):
        return Location(q, "coordinates", float(m[1]), float(m[2]))
    if key in AREA_ALIASES:
        name, lat, lng = AREA_ALIASES[key]
        return Location(name, "area", lat, lng)

    rows = (
        (
            await db.execute(
                text("""
            SELECT name, kind, lat, lng, score FROM (
                SELECT name, 'bus_stop' AS kind,
                       ST_Y(location::geometry) AS lat, ST_X(location::geometry) AS lng,
                       similarity(lower(name), :q) AS score
                FROM bus_stops
                UNION ALL
                SELECT name, 'train_station', ST_Y(location::geometry),
                       ST_X(location::geometry), similarity(lower(name), :q)
                FROM train_stations
                UNION ALL
                SELECT name, 'place', ST_Y(location::geometry), ST_X(location::geometry),
                       similarity(lower(name), :q)
                FROM places WHERE is_verified AND location IS NOT NULL
                UNION ALL
                SELECT area, 'area', avg(ST_Y(location::geometry)),
                       avg(ST_X(location::geometry)), similarity(lower(area), :q)
                FROM places WHERE is_verified AND location IS NOT NULL AND area IS NOT NULL
                GROUP BY area
            ) candidates
            WHERE score > 0.35
            ORDER BY score DESC, kind
            LIMIT 1
            """),
                {"q": key},
            )
        )
        .mappings()
        .first()
    )
    if rows is None:
        raise ToolError(
            f"Couldn't find a location called '{q}'. Use a bus stop, area or landmark "
            "name, or ask the user to be more specific."
        )
    return Location(rows["name"], rows["kind"], rows["lat"], rows["lng"])


async def resolve_place(db: AsyncSession, ref: str, ctx: ToolContext) -> Place:
    ref = ref.strip()
    place = None
    try:
        place = await db.get(Place, uuid.UUID(ref))
    except ValueError:
        place = (
            await db.execute(
                select(Place)
                .where(Place.is_verified.is_(True))
                .where(text("similarity(lower(places.name), :q) > 0.45"))
                .order_by(text("similarity(lower(places.name), :q) DESC"))
                .limit(1)
                .params(q=_norm(ref))
            )
        ).scalar_one_or_none()
    if place is None or not place.is_verified:
        raise ToolError(
            f"No place matches '{ref}'. Use a place_id from search_places results."
        )
    ctx.remember_place(place)
    return place


def _minutes(seconds: int) -> int:
    return max(1, round(seconds / 60))


# ----------------------------------------------------------------- arguments


class SearchPlacesArgs(BaseModel):
    query: str = Field(
        min_length=2,
        max_length=200,
        description="What the user is looking for, in their words, e.g. 'biryani' "
        "or 'quiet cafe with good wifi'.",
    )
    category: Category | None = Field(None, description="Only this kind of place.")
    price_tier: PriceTier | None = Field(None, description="Only this price level.")
    near: str | None = Field(
        None,
        description="Bus stop, area or landmark to search around, e.g. 'Old Dhaka' "
        "or 'Mirpur 10'. Closer places rank higher.",
    )
    limit: int = Field(5, ge=1, le=8)


class PlaceArgs(BaseModel):
    place: str = Field(
        description="place_id from search_places, or the exact place name."
    )


class TripArgs(BaseModel):
    origin: str = Field(
        description="Where the trip starts: a bus stop, area or landmark name "
        "(e.g. 'Mirpur 10'), or 'current location'."
    )
    place: str = Field(
        description="Destination: place_id from search_places, or the exact place name."
    )


# -------------------------------------------------------------------- tools


async def search_places(
    db: AsyncSession, args: SearchPlacesArgs, ctx: ToolContext
) -> dict:
    near = await resolve_location(db, args.near, ctx) if args.near else None
    found = await hybrid_search_service.hybrid_search(
        db,
        args.query,
        category=args.category,
        price_tier=args.price_tier,
        near_lat=near.lat if near else None,
        near_lng=near.lng if near else None,
        limit=args.limit,
    )
    results = []
    for item in found.items:
        ctx.remember_place(item.model_dump())
        result = {
            "place_id": str(item.id),
            "name": item.name,
            "category": item.category,
            "area": item.area,
            "rating": item.avg_rating,
            "price_tier": item.price_tier,
        }
        if item.distance_m is not None:
            # Named so small models don't read it as distance from the trip origin.
            result["km_from_near"] = round(item.distance_m / 1000, 1)
        if item.match.review_snippet:
            result["review_says"] = item.match.review_snippet
        results.append(result)
    out: dict = {"results": results}
    if near:
        out["near"] = near.label()
    if not results:
        out["note"] = "No matching places. Try a broader query or drop filters."
    return out


async def get_place_details(
    db: AsyncSession, args: PlaceArgs, ctx: ToolContext
) -> dict:
    place = await resolve_place(db, args.place, ctx)
    details = {
        "place_id": str(place.id),
        "name": place.name,
        "category": place.category,
        "area": place.area,
        "address": place.address,
        "description": place.description,
        "price_tier": place.price_tier,
        "amenities": place.amenities or [],
        "opening_hours": place.opening_hours,
        "rating": float(place.avg_rating),
        "review_count": place.review_count,
    }
    summary = await summary_service.get_summary(db, place.id)
    if summary.status == "ready":
        details["reviewers_say"] = {
            "pros": [p.text for p in summary.pros],
            "cons": [p.text for p in summary.cons],
            "best_for": [p.text for p in summary.best_for],
        }
    return details


async def _trip(db: AsyncSession, args: TripArgs, ctx: ToolContext):
    origin = await resolve_location(db, args.origin, ctx)
    place = await resolve_place(db, args.place, ctx)
    if place.lat is None:
        raise ToolError(
            f"{place.name} has no map location, so routes can't be planned."
        )
    return origin, place, Point(origin.lat, origin.lng), Point(place.lat, place.lng)


def _remember_route(
    ctx: ToolContext, origin: Location, place: Place, route: dict
) -> None:
    ctx.routes.append(
        {
            "place_id": str(place.id),
            "place_name": place.name,
            "origin": origin.label(),
            **route,
        }
    )


def _bus_route(option) -> dict:
    walk_to, bus, walk_from = option.steps
    return {
        "mode": "bus",
        "bus": bus.route_name,
        "operator": bus.operator,
        "board_at": bus.from_stop,
        "get_off_at": bus.to_stop,
        "stops": bus.num_stops,
        "fare_bdt": bus.fare,
        "walk_to_stop_m": walk_to.distance_m,
        "walk_from_stop_m": walk_from.distance_m,
        "duration_min": _minutes(option.total_duration_s),
    }


async def get_bus_route(db: AsyncSession, args: TripArgs, ctx: ToolContext) -> dict:
    origin, place, start, end = await _trip(db, args, ctx)
    option = await directions_service.bus_option(db, start, end)
    out = {"origin": origin.label(), "destination": place.name}
    if option is None:
        return out | {
            "available": False,
            "reason": "No single bus route serves stops within 1 km of both ends.",
        }
    route = _bus_route(option)
    _remember_route(ctx, origin, place, route)
    return out | {"available": True, "route": route}


def _ride_hail(option) -> dict:
    return {
        "mode": "ride_hail",
        "distance_km": round(option.distance_m / 1000, 1),
        "duration_min": _minutes(option.total_duration_s),
        "providers": [
            {"name": p.name, "fare_low_bdt": p.cost_low, "fare_high_bdt": p.cost_high}
            for p in option.providers
        ],
        "fare_bdt": option.total_cost,
    }


async def get_ridehail_estimate(
    db: AsyncSession, args: TripArgs, ctx: ToolContext
) -> dict:
    origin, place, start, end = await _trip(db, args, ctx)
    straight = directions_service.haversine_m(start, end)
    route = _ride_hail(
        await directions_service.ride_hail_option(db, start, end, straight)
    )
    _remember_route(ctx, origin, place, route)
    return {"origin": origin.label(), "destination": place.name, "estimate": route}


async def get_fare(db: AsyncSession, args: TripArgs, ctx: ToolContext) -> dict:
    """Every way to make the trip, cheapest first."""
    origin, place, start, end = await _trip(db, args, ctx)
    directions = await directions_service.get_directions(
        db, place.id, origin.lat, origin.lng
    )
    options = []
    for option in directions.options:
        if option.mode == "bus":
            route = _bus_route(option)
        elif option.mode == "ride_hail":
            route = _ride_hail(option)
        elif option.mode == "train":
            route = {
                "mode": "train",
                "from_station": option.from_station,
                "to_station": option.to_station,
                "next_departure": option.next_departure,
                "fare_bdt": option.fare,
                "duration_min": _minutes(option.total_duration_s),
            }
        else:
            route = {
                "mode": "walk",
                "distance_km": round(option.distance_m / 1000, 1),
                "fare_bdt": 0,
                "duration_min": _minutes(option.total_duration_s),
                "recommended": option.recommended,
            }
        if option.label:
            route["label"] = option.label
        options.append(route)
        if option.mode != "walk" or option.recommended:
            _remember_route(ctx, origin, place, route)
    # Cheapest first, but a walk too long to recommend isn't a real option.
    options.sort(
        key=lambda r: (
            r["mode"] == "walk" and not r["recommended"],
            r["fare_bdt"],
            r["duration_min"],
        )
    )
    return {
        "origin": origin.label(),
        "destination": place.name,
        "straight_line_km": round(directions.distance_m / 1000, 1),
        "options": options,
    }


# ----------------------------------------------------------------- registry


@dataclass
class Tool:
    spec: ToolSpec
    args_model: type[BaseModel]
    handler: Callable[[AsyncSession, BaseModel, ToolContext], Awaitable[dict]]


def _schema(model: type[BaseModel]) -> dict:
    """Pydantic's schema, simplified for picky tool-calling APIs: no titles,
    and optional fields as their plain type instead of anyOf[..., null]."""
    schema = model.model_json_schema()
    props = {}
    for name, prop in schema["properties"].items():
        prop = {k: v for k, v in prop.items() if k != "title"}
        if "anyOf" in prop:
            variant = next(v for v in prop.pop("anyOf") if v.get("type") != "null")
            prop = variant | {k: v for k, v in prop.items() if k != "default"}
        props[name] = prop
    return {
        "type": "object",
        "properties": props,
        "required": schema.get("required", []),
    }


def _tool(name: str, description: str, args_model, handler) -> Tool:
    return Tool(ToolSpec(name, description, _schema(args_model)), args_model, handler)


TOOLS: dict[str, Tool] = {
    t.spec.name: t
    for t in [
        _tool(
            "search_places",
            "Find places in Dhaka by what the user wants (food, vibe, amenities), "
            "optionally near an area. Returns place_ids to use with other tools. "
            "Results have no opening hours or reviews: use get_place_details.",
            SearchPlacesArgs,
            search_places,
        ),
        _tool(
            "get_place_details",
            "Details of one place: description, amenities, opening hours, rating, "
            "and a summary of what reviewers say.",
            PlaceArgs,
            get_place_details,
        ),
        _tool(
            "get_fare",
            "Compare every way to get from an origin to a place: bus, ride-hail, "
            "train and walking, with fares in taka and times. Use for 'cheapest' "
            "or 'fastest' questions.",
            TripArgs,
            get_fare,
        ),
        _tool(
            "get_bus_route",
            "The best single bus route from an origin to a place: which bus, where "
            "to get on and off, fare and time.",
            TripArgs,
            get_bus_route,
        ),
        _tool(
            "get_ridehail_estimate",
            "Uber/Pathao/Obhai fare range and travel time from an origin to a place.",
            TripArgs,
            get_ridehail_estimate,
        ),
    ]
}
