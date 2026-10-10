"""Transport data management: manual CRUD plus bulk CSV import.

CSV formats (header row required):

  bus_stops:  name,lat,lng[,district]
  bus_routes: name,operator,typical_fare,typical_duration_min,stops
              where `stops` is stop names in order, separated by "|"

Imports are all-or-nothing: any invalid row aborts the whole file and the
response lists every error with its line number.
"""

import csv
import io
import uuid
from datetime import time
from typing import Literal

from fastapi import APIRouter, HTTPException, UploadFile
from geoalchemy2.elements import WKTElement
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.deps import DB, AdminUserID
from app.models.transport import (
    BusRoute,
    BusStop,
    TrainSchedule,
    TrainStation,
    TransportFare,
)
from app.services.admin_service import log_action

router = APIRouter()

MAX_CSV_BYTES = 2 * 1024 * 1024


class BusStopCreate(BaseModel):
    name: str = Field(min_length=1)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    division: str | None = None
    district: str | None = None


class BusRouteCreate(BaseModel):
    name: str = Field(min_length=1)
    operator: str | None = None
    stop_ids: list[uuid.UUID] = Field(min_length=2)
    typical_fare: int = Field(ge=0)
    typical_duration_min: int = Field(gt=0)


class TrainStationCreate(BaseModel):
    name: str = Field(min_length=1)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    division: str | None = None


class TrainScheduleCreate(BaseModel):
    from_station_id: uuid.UUID
    to_station_id: uuid.UUID
    departure_time: time
    duration_min: int = Field(gt=0)
    fare: int = Field(ge=0)
    days_of_week: list[int] = Field(min_length=1)


class FareCreate(BaseModel):
    provider: Literal["uber", "pathao", "obhai"]
    base_fare: int = Field(ge=0)
    per_km: int = Field(ge=0)
    per_min: int = Field(ge=0)


def _point(lat: float, lng: float) -> WKTElement:
    return WKTElement(f"POINT({lng} {lat})", srid=4326)


@router.get("/transport/summary")
async def transport_summary(db: DB, _admin: AdminUserID):
    async def count(model):
        return (await db.execute(select(func.count()).select_from(model))).scalar_one()

    return {
        "bus_stops": await count(BusStop),
        "bus_routes": await count(BusRoute),
        "train_stations": await count(TrainStation),
        "train_schedules": await count(TrainSchedule),
        "fares": await count(TransportFare),
    }


@router.post("/bus-stops", status_code=201)
async def create_bus_stop(body: BusStopCreate, db: DB, admin: AdminUserID):
    stop = BusStop(
        name=body.name,
        location=_point(body.lat, body.lng),
        division=body.division,
        district=body.district,
    )
    db.add(stop)
    await db.flush()
    log_action(db, admin, "create_bus_stop", "bus_stop", stop.id)
    await db.commit()
    return {"id": str(stop.id)}


@router.post("/bus-routes", status_code=201)
async def create_bus_route(body: BusRouteCreate, db: DB, admin: AdminUserID):
    found = (
        await db.execute(select(func.count()).where(BusStop.id.in_(body.stop_ids)))
    ).scalar_one()
    if found != len(set(body.stop_ids)):
        raise HTTPException(status_code=422, detail="Unknown bus stop id in stop_ids")
    route = BusRoute(
        name=body.name,
        operator=body.operator,
        stops=[str(s) for s in body.stop_ids],
        typical_fare=body.typical_fare,
        typical_duration_min=body.typical_duration_min,
    )
    db.add(route)
    await db.flush()
    log_action(db, admin, "create_bus_route", "bus_route", route.id)
    await db.commit()
    return {"id": str(route.id)}


@router.post("/train-stations", status_code=201)
async def create_train_station(body: TrainStationCreate, db: DB, admin: AdminUserID):
    station = TrainStation(
        name=body.name, location=_point(body.lat, body.lng), division=body.division
    )
    db.add(station)
    await db.flush()
    log_action(db, admin, "create_train_station", "train_station", station.id)
    await db.commit()
    return {"id": str(station.id)}


@router.post("/train-schedules", status_code=201)
async def create_train_schedule(body: TrainScheduleCreate, db: DB, admin: AdminUserID):
    if any(d < 1 or d > 7 for d in body.days_of_week):
        raise HTTPException(
            status_code=422, detail="days_of_week uses 1 (Mon) .. 7 (Sun)"
        )
    schedule = TrainSchedule(**body.model_dump())
    db.add(schedule)
    await db.flush()
    log_action(db, admin, "create_train_schedule", "train_schedule", schedule.id)
    await db.commit()
    return {"id": str(schedule.id)}


@router.post("/transport-fares", status_code=201)
async def upsert_fare(body: FareCreate, db: DB, admin: AdminUserID):
    fare = (
        await db.execute(
            select(TransportFare).where(TransportFare.provider == body.provider)
        )
    ).scalar_one_or_none()
    if fare:
        fare.base_fare, fare.per_km, fare.per_min = (
            body.base_fare,
            body.per_km,
            body.per_min,
        )
    else:
        fare = TransportFare(**body.model_dump())
        db.add(fare)
    await db.flush()
    log_action(db, admin, "upsert_fare", "transport_fare", fare.id, body.model_dump())
    await db.commit()
    return {"id": str(fare.id)}


async def _read_csv(file: UploadFile, required: set[str]) -> list[tuple[int, dict]]:
    raw = await file.read(MAX_CSV_BYTES + 1)
    if len(raw) > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail="CSV too large (max 2 MB)")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="CSV must be UTF-8") from None
    reader = csv.DictReader(io.StringIO(text))
    headers = {h.strip() for h in (reader.fieldnames or [])}
    if missing := required - headers:
        raise HTTPException(
            status_code=422, detail=f"Missing columns: {', '.join(sorted(missing))}"
        )
    return [
        (line, {k.strip(): (v or "").strip() for k, v in row.items() if k})
        for line, row in enumerate(reader, start=2)
    ]


@router.post("/transport/import/bus-stops")
async def import_bus_stops(file: UploadFile, db: DB, admin: AdminUserID):
    """Upsert stops by name."""
    rows = await _read_csv(file, {"name", "lat", "lng"})
    errors, parsed = [], []
    for line, r in rows:
        try:
            parsed.append(
                BusStopCreate(
                    name=r["name"],
                    lat=r["lat"],
                    lng=r["lng"],
                    district=r.get("district") or None,
                )
            )
        except ValueError as exc:
            errors.append({"line": line, "error": str(exc).splitlines()[0]})
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})

    existing = {
        s.name.lower(): s for s in (await db.execute(select(BusStop))).scalars().all()
    }
    created = updated = 0
    for s in parsed:
        if stop := existing.get(s.name.lower()):
            stop.location = _point(s.lat, s.lng)
            stop.district = s.district or stop.district
            updated += 1
        else:
            stop = BusStop(
                name=s.name, location=_point(s.lat, s.lng), district=s.district
            )
            db.add(stop)
            existing[s.name.lower()] = stop
            created += 1
    log_action(
        db,
        admin,
        "import_bus_stops",
        None,
        None,
        {"created": created, "updated": updated},
    )
    await db.commit()
    return {"created": created, "updated": updated}


@router.post("/transport/import/bus-routes")
async def import_bus_routes(file: UploadFile, db: DB, admin: AdminUserID):
    """Upsert routes by name. Stops are referenced by name and must already exist."""
    rows = await _read_csv(
        file, {"name", "operator", "typical_fare", "typical_duration_min", "stops"}
    )
    stops_by_name = {
        s.name.lower(): s.id
        for s in (await db.execute(select(BusStop))).scalars().all()
    }
    errors, parsed = [], []
    for line, r in rows:
        names = [n.strip() for n in r["stops"].split("|") if n.strip()]
        unknown = [n for n in names if n.lower() not in stops_by_name]
        if unknown:
            errors.append(
                {"line": line, "error": f"Unknown stops: {', '.join(unknown)}"}
            )
            continue
        try:
            parsed.append(
                BusRouteCreate(
                    name=r["name"],
                    operator=r["operator"] or None,
                    typical_fare=r["typical_fare"],
                    typical_duration_min=r["typical_duration_min"],
                    stop_ids=[stops_by_name[n.lower()] for n in names],
                )
            )
        except ValueError as exc:
            errors.append({"line": line, "error": str(exc).splitlines()[0]})
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})

    existing = {
        r.name.lower(): r for r in (await db.execute(select(BusRoute))).scalars().all()
    }
    created = updated = 0
    for b in parsed:
        values = {
            "operator": b.operator,
            "stops": [str(s) for s in b.stop_ids],
            "typical_fare": b.typical_fare,
            "typical_duration_min": b.typical_duration_min,
        }
        if route := existing.get(b.name.lower()):
            for k, v in values.items():
                setattr(route, k, v)
            updated += 1
        else:
            db.add(BusRoute(name=b.name, **values))
            created += 1
    log_action(
        db,
        admin,
        "import_bus_routes",
        None,
        None,
        {"created": created, "updated": updated},
    )
    await db.commit()
    return {"created": created, "updated": updated}
