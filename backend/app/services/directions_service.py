""" "How to get there": bus, ride-hail, train and walking options.

All distances are computed in PostGIS on geography columns (meters). Road
distance is approximated as straight-line distance times DETOUR_FACTOR unless
a Google Maps key is configured, in which case driving distance and live
traffic duration come from the Directions API.
"""

import logging
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import httpx
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas.directions import (
    BusOption,
    BusStep,
    DirectionsResponse,
    RideHailOption,
    RideHailProvider,
    TrainOption,
    TrainStep,
    WalkOption,
    WalkStep,
)

log = logging.getLogger(__name__)

DHAKA_TZ = ZoneInfo("Asia/Dhaka")
WALK_SPEED_MPS = 1.3  # ~4.7 km/h, accounts for crossings and crowded footpaths
DETOUR_FACTOR = 1.35  # road distance / straight-line distance, typical for Dhaka
CITY_DRIVE_KMH = 15  # average Dhaka car speed in traffic
BUS_WAIT_S = 5 * 60
MIN_BUS_FARE = 10  # BRTA minimum fare
STOP_SEARCH_RADIUS_M = 1000
STATION_SEARCH_RADIUS_M = 2000
WALK_RECOMMENDED_MAX_M = 1500

DEFAULT_FARES = [
    {"provider": "uber", "base_fare": 50, "per_km": 18, "per_min": 2},
    {"provider": "pathao", "base_fare": 40, "per_km": 16, "per_min": 2},
]


@dataclass
class Point:
    lat: float
    lng: float

    @property
    def wkt(self) -> str:
        return f"SRID=4326;POINT({self.lng} {self.lat})"


def haversine_m(a: Point, b: Point) -> int:
    r = 6_371_000
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp, dl = p2 - p1, math.radians(b.lng - a.lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return int(2 * r * math.asin(math.sqrt(h)))


def _walk(to: str, meters: float) -> WalkStep:
    meters = int(meters * 1.2)  # footpath detours
    return WalkStep(to=to, distance_m=meters, duration_s=int(meters / WALK_SPEED_MPS))


async def get_directions(
    db: AsyncSession, place_id: uuid.UUID, from_lat: float, from_lng: float
) -> DirectionsResponse:
    row = (
        (
            await db.execute(
                text("""
            SELECT ST_Y(location::geometry) AS lat, ST_X(location::geometry) AS lng
            FROM places WHERE id = :id
            """),
                {"id": place_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Place not found"
        )
    if row["lat"] is None:
        raise HTTPException(
            status_code=422,
            detail="This place has no location yet",
        )

    origin = Point(from_lat, from_lng)
    dest = Point(row["lat"], row["lng"])
    distance_m = haversine_m(origin, dest)

    options: list = []
    if bus := await bus_option(db, origin, dest):
        options.append(bus)
    options.append(await ride_hail_option(db, origin, dest, distance_m))
    if train := await train_option(db, origin, dest):
        options.append(train)
    walk_m = int(distance_m * 1.2)
    options.append(
        WalkOption(
            distance_m=walk_m,
            duration_s=int(walk_m / WALK_SPEED_MPS),
            total_duration_s=int(walk_m / WALK_SPEED_MPS),
            recommended=walk_m <= WALK_RECOMMENDED_MAX_M,
        )
    )
    _label(options)
    return DirectionsResponse(distance_m=distance_m, options=options)


def _label(options: list) -> None:
    """Tag the cheapest paid option and the fastest option overall."""
    paid = [o for o in options if o.mode != "walk"]
    if paid:
        min(paid, key=lambda o: (o.total_cost, o.total_duration_s)).label = "Cheapest"
    fastest = min(options, key=lambda o: o.total_duration_s)
    fastest.label = "Fastest" if fastest.label is None else f"{fastest.label} & fastest"


async def _nearby(db: AsyncSession, table: str, p: Point, radius: int, limit: int):
    # `table` is always a literal from this module, never user input.
    return (
        (
            await db.execute(
                text(f"""
            SELECT id, name, ST_Distance(location, CAST(:pt AS geography)) AS dist
            FROM {table}
            WHERE ST_DWithin(location, CAST(:pt AS geography), :radius)
            ORDER BY dist
            LIMIT :limit
            """),
                {"pt": p.wkt, "radius": radius, "limit": limit},
            )
        )
        .mappings()
        .all()
    )


async def bus_option(db: AsyncSession, origin: Point, dest: Point) -> BusOption | None:
    """Best single-route bus trip between stops within walking distance of each end.

    For every route serving both a stop near the origin and a stop near the
    destination, every (boarding, alighting) pair is scored by total door-to-door
    time; fare and ride time are prorated by how much of the route is ridden.
    """
    o_stops = await _nearby(db, "bus_stops", origin, STOP_SEARCH_RADIUS_M, 5)
    d_stops = await _nearby(db, "bus_stops", dest, STOP_SEARCH_RADIUS_M, 5)
    if not o_stops or not d_stops:
        return None
    o_by_id = {str(s["id"]): s for s in o_stops}
    d_by_id = {str(s["id"]): s for s in d_stops}

    routes = (
        (
            await db.execute(
                text("""
            SELECT name, operator, stops::text[] AS stops, typical_fare, typical_duration_min
            FROM bus_routes
            WHERE stops && CAST(:o AS uuid[]) AND stops && CAST(:d AS uuid[])
            """),
                {"o": list(o_by_id), "d": list(d_by_id)},
            )
        )
        .mappings()
        .all()
    )

    best = None
    for route in routes:
        stops = route["stops"]
        hops_total = max(len(stops) - 1, 1)
        for i, sid in enumerate(stops):
            if sid not in o_by_id:
                continue
            for j, did in enumerate(stops):
                # Routes run in both directions, so either order is a valid ride.
                if did not in d_by_id or i == j:
                    continue
                fraction = abs(j - i) / hops_total
                ride_s = max(int(route["typical_duration_min"] * 60 * fraction), 180)
                fare = max(MIN_BUS_FARE, round(route["typical_fare"] * fraction))
                walk_to = _walk(o_by_id[sid]["name"], o_by_id[sid]["dist"])
                walk_from = _walk("destination", d_by_id[did]["dist"])
                total_s = (
                    walk_to.duration_s + BUS_WAIT_S + ride_s + walk_from.duration_s
                )
                if best is None or total_s < best[0]:
                    best = (
                        total_s,
                        fare,
                        route,
                        sid,
                        did,
                        abs(j - i),
                        ride_s,
                        walk_to,
                        walk_from,
                    )

    if best is None:
        return None
    total_s, fare, route, sid, did, n_stops, ride_s, walk_to, walk_from = best
    return BusOption(
        steps=[
            walk_to,
            BusStep(
                route_name=route["name"],
                operator=route["operator"],
                from_stop=o_by_id[sid]["name"],
                to_stop=d_by_id[did]["name"],
                num_stops=n_stops,
                duration_s=ride_s + BUS_WAIT_S,
                fare=fare,
            ),
            walk_from,
        ],
        total_cost=fare,
        total_duration_s=total_s,
    )


async def _google_drive_estimate(origin: Point, dest: Point) -> tuple[int, int] | None:
    """(road meters, seconds in current traffic) from Google, or None."""
    if not settings.GOOGLE_MAPS_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            resp = await client.get(
                "https://maps.googleapis.com/maps/api/directions/json",
                params={
                    "origin": f"{origin.lat},{origin.lng}",
                    "destination": f"{dest.lat},{dest.lng}",
                    "mode": "driving",
                    "departure_time": "now",
                    "key": settings.GOOGLE_MAPS_API_KEY,
                },
            )
        leg = resp.json()["routes"][0]["legs"][0]
        duration = leg.get("duration_in_traffic", leg["duration"])["value"]
        return leg["distance"]["value"], duration
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        log.warning("Google Directions lookup failed: %s", exc)
        return None


async def ride_hail_option(
    db: AsyncSession, origin: Point, dest: Point, straight_m: int
) -> RideHailOption:
    fares = (
        await db.execute(
            text(
                "SELECT provider, base_fare, per_km, per_min FROM transport_fares ORDER BY provider"
            )
        )
    ).mappings().all() or DEFAULT_FARES

    estimate = await _google_drive_estimate(origin, dest)
    if estimate:
        road_m, duration_s = estimate
    else:
        road_m = int(straight_m * DETOUR_FACTOR)
        duration_s = int(road_m / (CITY_DRIVE_KMH * 1000 / 3600))
    km, minutes = road_m / 1000, duration_s / 60

    providers = []
    for f in fares:
        low = round(f["base_fare"] + f["per_km"] * km + f["per_min"] * minutes)
        providers.append(
            RideHailProvider(
                name=f["provider"],
                cost_low=low,
                cost_high=round(low * 1.3),  # typical surge headroom
                duration_s=duration_s,
            )
        )
    providers.sort(key=lambda p: p.cost_low)
    return RideHailOption(
        providers=providers,
        distance_m=road_m,
        total_cost=providers[0].cost_low,
        total_duration_s=duration_s,
    )


def _next_departure(
    departures: list[tuple[time, list[int]]], now: datetime
) -> str | None:
    """Next departure today or later this week. days_of_week uses ISO weekday
    numbers (1=Mon .. 7=Sun)."""
    for day_offset in range(8):
        weekday = (now.isoweekday() - 1 + day_offset) % 7 + 1
        candidates = sorted(
            t
            for t, days in departures
            if weekday in days and (day_offset > 0 or t > now.time())
        )
        if candidates:
            hhmm = candidates[0].strftime("%H:%M")
            if day_offset == 0:
                return hhmm
            if day_offset == 1:
                return f"tomorrow {hhmm}"
            return f"{(now + timedelta(days=day_offset)).strftime('%a')} {hhmm}"
    return None


async def train_option(
    db: AsyncSession, origin: Point, dest: Point
) -> TrainOption | None:
    o_station = await _nearby(db, "train_stations", origin, STATION_SEARCH_RADIUS_M, 1)
    d_station = await _nearby(db, "train_stations", dest, STATION_SEARCH_RADIUS_M, 1)
    if not o_station or not d_station or o_station[0]["id"] == d_station[0]["id"]:
        return None
    o, d = o_station[0], d_station[0]

    schedules = (
        (
            await db.execute(
                text("""
            SELECT departure_time, duration_min, fare, days_of_week
            FROM train_schedules
            WHERE from_station_id = :o AND to_station_id = :d
            ORDER BY fare
            """),
                {"o": o["id"], "d": d["id"]},
            )
        )
        .mappings()
        .all()
    )
    if not schedules:
        return None

    next_dep = _next_departure(
        [(s["departure_time"], s["days_of_week"]) for s in schedules],
        datetime.now(DHAKA_TZ),
    )
    s = schedules[0]
    walk_to = _walk(o["name"], o["dist"])
    walk_from = _walk("destination", d["dist"])
    ride_s = s["duration_min"] * 60
    return TrainOption(
        steps=[
            walk_to,
            TrainStep(
                from_station=o["name"],
                to_station=d["name"],
                departure_time=next_dep,
                duration_s=ride_s,
                fare=s["fare"],
            ),
            walk_from,
        ],
        from_station=o["name"],
        to_station=d["name"],
        next_departure=next_dep,
        fare=s["fare"],
        duration_s=ride_s,
        total_cost=s["fare"],
        total_duration_s=walk_to.duration_s + ride_s + walk_from.duration_s,
    )
