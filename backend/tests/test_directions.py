from datetime import datetime, time

import pytest
from geoalchemy2.elements import WKTElement

from app.db.session import AsyncSessionLocal
from app.models.transport import (
    BusRoute,
    BusStop,
    TrainSchedule,
    TrainStation,
    TransportFare,
)
from app.services.directions_service import DHAKA_TZ, _next_departure


def _pt(lat, lng):
    return WKTElement(f"POINT({lng} {lat})", srid=4326)


@pytest.fixture
async def transport():
    """A five-stop line running north-south, plus a rail link."""
    async with AsyncSessionLocal() as db:
        stops = [
            BusStop(name=name, location=_pt(lat, 90.40))
            for name, lat in [
                ("North", 23.80),
                ("N2", 23.79),
                ("Mid", 23.78),
                ("S2", 23.77),
                ("South", 23.76),
            ]
        ]
        db.add_all(stops)
        await db.flush()
        db.add(
            BusRoute(
                name="Line 1",
                operator="BRTC",
                stops=[str(s.id) for s in stops],
                typical_fare=40,
                typical_duration_min=40,
            )
        )
        a = TrainStation(name="Station A", location=_pt(23.80, 90.42))
        b = TrainStation(name="Station B", location=_pt(23.70, 90.42))
        db.add_all([a, b])
        await db.flush()
        db.add(
            TrainSchedule(
                from_station_id=a.id,
                to_station_id=b.id,
                departure_time=time(8, 0),
                duration_min=20,
                fare=30,
                days_of_week=[1, 2, 3, 4, 5, 6, 7],
            )
        )
        db.add(TransportFare(provider="uber", base_fare=50, per_km=18, per_min=2))
        await db.commit()


async def _directions(client, place, lat, lng):
    resp = await client.get(
        f"/api/v1/places/{place.id}/directions",
        params={"from_lat": lat, "from_lng": lng},
    )
    assert resp.status_code == 200, resp.text
    return {o["mode"]: o for o in resp.json()["options"]}


async def test_bus_route_prorates_fare_and_time(client, transport, make_place):
    # Origin next to "North", destination next to "Mid": half the line.
    place = await make_place(lat=23.7802, lng=90.4002)
    options = await _directions(client, place, 23.8001, 90.4001)

    bus = options["bus"]
    walk_to, ride, walk_from = bus["steps"]
    assert (ride["from_stop"], ride["to_stop"], ride["num_stops"]) == (
        "North",
        "Mid",
        2,
    )
    assert ride["fare"] == 20  # half of the ৳40 line fare
    assert walk_to["distance_m"] < 50 and walk_from["distance_m"] < 50
    assert bus["total_cost"] == 20
    assert bus["label"] and "Cheapest" in bus["label"]


async def test_bus_works_in_reverse_direction(client, transport, make_place):
    place = await make_place(lat=23.8001, lng=90.4001)
    options = await _directions(client, place, 23.7601, 90.4001)
    ride = options["bus"]["steps"][1]
    assert (ride["from_stop"], ride["to_stop"], ride["num_stops"]) == (
        "South",
        "North",
        4,
    )
    assert ride["fare"] == 40


async def test_no_bus_when_no_stop_nearby(client, transport, make_place):
    place = await make_place(lat=23.7802, lng=90.4002)
    options = await _directions(client, place, 23.90, 90.30)  # ~15 km away, no stops
    assert "bus" not in options
    assert "ride_hail" in options and "walk" in options


async def test_ride_hail_estimate(client, transport, make_place):
    place = await make_place(lat=23.7802, lng=90.4002)
    options = await _directions(client, place, 23.8001, 90.4001)
    uber = options["ride_hail"]["providers"][0]
    assert uber["name"] == "uber"
    assert 50 < uber["cost_low"] < uber["cost_high"]
    # ~2.2 km straight line -> ~3 km road at 15 km/h -> ~12 minutes
    assert 8 * 60 < uber["duration_s"] < 16 * 60


async def test_train_option(client, transport, make_place):
    place = await make_place(lat=23.7001, lng=90.4201)
    options = await _directions(client, place, 23.8001, 90.4201)
    train = options["train"]
    assert (train["from_station"], train["to_station"], train["fare"]) == (
        "Station A",
        "Station B",
        30,
    )
    assert train["next_departure"] is not None


async def test_walk_recommended_only_when_close(client, transport, make_place):
    place = await make_place(lat=23.7802, lng=90.4002)
    near = await _directions(client, place, 23.7810, 90.4002)
    far = await _directions(client, place, 23.8001, 90.4001)
    assert near["walk"]["recommended"] is True
    assert far["walk"]["recommended"] is False


async def test_exactly_one_fastest_label(client, transport, make_place):
    place = await make_place(lat=23.7802, lng=90.4002)
    resp = await client.get(
        f"/api/v1/places/{place.id}/directions",
        params={"from_lat": 23.8001, "from_lng": 90.4001},
    )
    labels = [o["label"] for o in resp.json()["options"] if o["label"]]
    assert sum("astest" in label for label in labels) == 1


async def test_place_without_location(client, make_place):
    place = await make_place(lat=None, lng=None)
    resp = await client.get(
        f"/api/v1/places/{place.id}/directions",
        params={"from_lat": 23.8, "from_lng": 90.4},
    )
    assert resp.status_code == 422


async def test_invalid_coordinates(client, make_place):
    place = await make_place()
    resp = await client.get(
        f"/api/v1/places/{place.id}/directions",
        params={"from_lat": 123, "from_lng": 90.4},
    )
    assert resp.status_code == 422


def test_next_departure_rolls_over_to_tomorrow():
    sched = [(time(8, 0), [1, 2, 3, 4, 5, 6, 7]), (time(18, 0), [1, 2, 3, 4, 5, 6, 7])]
    morning = datetime(2026, 10, 12, 7, 0, tzinfo=DHAKA_TZ)  # a Monday
    evening = datetime(2026, 10, 12, 19, 0, tzinfo=DHAKA_TZ)
    assert _next_departure(sched, morning) == "08:00"
    assert _next_departure(sched, evening) == "tomorrow 08:00"


def test_next_departure_respects_weekdays():
    friday_only = [(time(9, 0), [5])]
    monday = datetime(2026, 10, 12, 10, 0, tzinfo=DHAKA_TZ)
    assert _next_departure(friday_only, monday) == "Fri 09:00"
    assert _next_departure([], monday) is None
