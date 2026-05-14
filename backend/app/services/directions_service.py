import math
import uuid

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas.directions import (
    BusOption, BusStep, DirectionsResponse, RideHailOption, RideHailProvider,
    TrainOption, WalkOption, WalkStep,
)


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return int(2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


WALK_SPEED_MPS = 1.4  # ~5 km/h


async def get_directions(
    db: AsyncSession,
    place_id: uuid.UUID,
    from_lat: float,
    from_lng: float,
) -> DirectionsResponse:
    place_row = await db.execute(
        text("SELECT ST_Y(location::geometry) as lat, ST_X(location::geometry) as lng FROM places WHERE id = :id"),
        {"id": str(place_id)},
    )
    place = place_row.mappings().one_or_none()
    if not place:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Place not found")

    to_lat, to_lng = place["lat"], place["lng"]
    distance_m = _haversine_m(from_lat, from_lng, to_lat, to_lng)

    options = []

    bus_option = await _bus_option(db, from_lat, from_lng, to_lat, to_lng)
    if bus_option:
        options.append(bus_option)

    ride_hail = await _ride_hail_option(db, from_lat, from_lng, to_lat, to_lng, distance_m)
    if ride_hail:
        options.append(ride_hail)

    train_option = await _train_option(db, from_lat, from_lng, to_lat, to_lng)
    if train_option:
        options.append(train_option)

    walk_duration_s = int(distance_m / WALK_SPEED_MPS)
    options.append(WalkOption(duration_s=walk_duration_s, recommended=distance_m < 2000))

    return DirectionsResponse(distance_m=distance_m, options=options)


async def _bus_option(db: AsyncSession, from_lat: float, from_lng: float, to_lat: float, to_lng: float) -> BusOption | None:
    origin_stops = await db.execute(text("""
        SELECT id, name, ST_Y(location::geometry) as lat, ST_X(location::geometry) as lng
        FROM bus_stops
        WHERE ST_DWithin(location, ST_GeogFromText(:pt), 1000)
        ORDER BY ST_Distance(location, ST_GeogFromText(:pt))
        LIMIT 3
    """), {"pt": f"POINT({from_lng} {from_lat})"})
    origin_stops = origin_stops.mappings().all()
    if not origin_stops:
        return None

    dest_stops = await db.execute(text("""
        SELECT id, name, ST_Y(location::geometry) as lat, ST_X(location::geometry) as lng
        FROM bus_stops
        WHERE ST_DWithin(location, ST_GeogFromText(:pt), 1000)
        ORDER BY ST_Distance(location, ST_GeogFromText(:pt))
        LIMIT 3
    """), {"pt": f"POINT({to_lng} {to_lat})"})
    dest_stops = dest_stops.mappings().all()
    if not dest_stops:
        return None

    origin_ids = [str(s["id"]) for s in origin_stops]
    dest_ids = [str(s["id"]) for s in dest_stops]

    route_row = await db.execute(text("""
        SELECT id, name, stops, typical_fare, typical_duration_min
        FROM bus_routes
        WHERE stops && ARRAY[:o1]::uuid[]
          AND stops && ARRAY[:d1]::uuid[]
        LIMIT 1
    """), {"o1": origin_ids[0], "d1": dest_ids[0]})
    route = route_row.mappings().one_or_none()
    if not route:
        return None

    origin_stop = origin_stops[0]
    dest_stop = dest_stops[0]

    walk_to_m = _haversine_m(from_lat, from_lng, origin_stop["lat"], origin_stop["lng"])
    walk_from_m = _haversine_m(dest_stop["lat"], dest_stop["lng"], to_lat, to_lng)

    steps = [
        WalkStep(to=origin_stop["name"], distance_m=walk_to_m, duration_s=int(walk_to_m / WALK_SPEED_MPS)),
        BusStep(route_name=route["name"], from_stop=origin_stop["name"], to_stop=dest_stop["name"],
                duration_s=route["typical_duration_min"] * 60, fare=route["typical_fare"]),
        WalkStep(to="destination", distance_m=walk_from_m, duration_s=int(walk_from_m / WALK_SPEED_MPS)),
    ]
    total_duration = sum(getattr(s, "duration_s", 0) for s in steps)
    return BusOption(steps=steps, total_cost=route["typical_fare"], total_duration_s=total_duration)


async def _ride_hail_option(db: AsyncSession, from_lat: float, from_lng: float, to_lat: float, to_lng: float, distance_m: int) -> RideHailOption | None:
    fares_r = await db.execute(text("SELECT provider, base_fare, per_km, per_min FROM transport_fares"))
    fares = fares_r.mappings().all()
    if not fares:
        dist_km = distance_m / 1000
        fares = [
            {"provider": "uber", "base_fare": 50, "per_km": 18, "per_min": 2},
            {"provider": "pathao", "base_fare": 40, "per_km": 16, "per_min": 2},
        ]

    duration_s = 1080
    if settings.GOOGLE_MAPS_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    "https://maps.googleapis.com/maps/api/directions/json",
                    params={"origin": f"{from_lat},{from_lng}", "destination": f"{to_lat},{to_lng}",
                            "mode": "driving", "key": settings.GOOGLE_MAPS_API_KEY},
                )
                data = resp.json()
                if data.get("routes"):
                    duration_s = data["routes"][0]["legs"][0]["duration"]["value"]
        except Exception:
            pass

    dist_km = distance_m / 1000
    providers = []
    for f in fares:
        low = int(f["base_fare"] + f["per_km"] * dist_km)
        high = int(low * 1.3)
        providers.append(RideHailProvider(name=f["provider"], cost_low=low, cost_high=high, duration_s=duration_s))

    return RideHailOption(providers=providers)


async def _train_option(db: AsyncSession, from_lat: float, from_lng: float, to_lat: float, to_lng: float) -> TrainOption | None:
    origin_station = await db.execute(text("""
        SELECT id, name FROM train_stations
        WHERE ST_DWithin(location, ST_GeogFromText(:pt), 3000)
        ORDER BY ST_Distance(location, ST_GeogFromText(:pt)) LIMIT 1
    """), {"pt": f"POINT({from_lng} {from_lat})"})
    origin = origin_station.mappings().one_or_none()
    if not origin:
        return None

    dest_station = await db.execute(text("""
        SELECT id, name FROM train_stations
        WHERE ST_DWithin(location, ST_GeogFromText(:pt), 3000)
        ORDER BY ST_Distance(location, ST_GeogFromText(:pt)) LIMIT 1
    """), {"pt": f"POINT({to_lng} {to_lat})"})
    dest = dest_station.mappings().one_or_none()
    if not dest or dest["id"] == origin["id"]:
        return None

    schedule = await db.execute(text("""
        SELECT fare, duration_min FROM train_schedules
        WHERE from_station_id = :from_id AND to_station_id = :to_id
        LIMIT 1
    """), {"from_id": str(origin["id"]), "to_id": str(dest["id"])})
    sched = schedule.mappings().one_or_none()
    if not sched:
        return None

    return TrainOption(from_station=origin["name"], to_station=dest["name"],
                       fare=sched["fare"], duration_s=sched["duration_min"] * 60)
