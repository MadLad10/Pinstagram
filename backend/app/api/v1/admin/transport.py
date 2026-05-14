from fastapi import APIRouter
from pydantic import BaseModel
from app.core.deps import AdminUserID, DB
from app.models.transport import BusStop, BusRoute, TrainStation, TrainSchedule, TransportFare

router = APIRouter()


class BusStopCreate(BaseModel):
    name: str
    lat: float
    lng: float
    division: str | None = None
    district: str | None = None


class BusRouteCreate(BaseModel):
    name: str
    operator: str | None = None
    stop_ids: list[str]
    typical_fare: int
    typical_duration_min: int


class TrainStationCreate(BaseModel):
    name: str
    lat: float
    lng: float
    division: str | None = None


class TrainScheduleCreate(BaseModel):
    from_station_id: str
    to_station_id: str
    departure_time: str
    duration_min: int
    fare: int
    days_of_week: list[int]


class FareCreate(BaseModel):
    provider: str
    base_fare: int
    per_km: int
    per_min: int


@router.post("/bus-stops", status_code=201)
async def create_bus_stop(body: BusStopCreate, db: DB, _admin: AdminUserID):
    from geoalchemy2.elements import WKTElement
    stop = BusStop(name=body.name, location=WKTElement(f"POINT({body.lng} {body.lat})", srid=4326),
                   division=body.division, district=body.district)
    db.add(stop)
    await db.commit()
    return {"id": str(stop.id)}


@router.post("/bus-routes", status_code=201)
async def create_bus_route(body: BusRouteCreate, db: DB, _admin: AdminUserID):
    import uuid
    route = BusRoute(name=body.name, operator=body.operator, stops=[uuid.UUID(s) for s in body.stop_ids],
                     typical_fare=body.typical_fare, typical_duration_min=body.typical_duration_min)
    db.add(route)
    await db.commit()
    return {"id": str(route.id)}


@router.post("/train-stations", status_code=201)
async def create_train_station(body: TrainStationCreate, db: DB, _admin: AdminUserID):
    from geoalchemy2.elements import WKTElement
    station = TrainStation(name=body.name, location=WKTElement(f"POINT({body.lng} {body.lat})", srid=4326), division=body.division)
    db.add(station)
    await db.commit()
    return {"id": str(station.id)}


@router.post("/train-schedules", status_code=201)
async def create_train_schedule(body: TrainScheduleCreate, db: DB, _admin: AdminUserID):
    import uuid
    from datetime import time
    h, m = map(int, body.departure_time.split(":"))
    schedule = TrainSchedule(from_station_id=uuid.UUID(body.from_station_id), to_station_id=uuid.UUID(body.to_station_id),
                             departure_time=time(h, m), duration_min=body.duration_min, fare=body.fare, days_of_week=body.days_of_week)
    db.add(schedule)
    await db.commit()
    return {"id": str(schedule.id)}


@router.post("/transport-fares", status_code=201)
async def create_fare(body: FareCreate, db: DB, _admin: AdminUserID):
    fare = TransportFare(provider=body.provider, base_fare=body.base_fare, per_km=body.per_km, per_min=body.per_min)
    db.add(fare)
    await db.commit()
    return {"id": str(fare.id)}
