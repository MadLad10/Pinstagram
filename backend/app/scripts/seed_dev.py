"""
Usage: python -m app.scripts.seed_dev
Seeds demo places, bus routes, transport fares, and a demo user.
"""
import asyncio
import uuid
from datetime import datetime, timezone

from geoalchemy2.elements import WKTElement
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.place import Place
from app.models.transport import BusStop, BusRoute, TransportFare
from app.models.user import User
from app.services.uploads_service import ensure_bucket_exists

PLACES = [
    {"name": "Cafe Mango", "category": "cafe", "address": "Road 11, Banani, Dhaka", "division": "Dhaka", "district": "Dhaka", "area": "Banani", "lat": 23.7937, "lng": 90.4066, "price_tier": "mid", "avg_rating": 4.2, "amenities": ["ac", "wifi"], "is_verified": True},
    {"name": "Star Kabab & Restaurant", "category": "restaurant", "address": "Dhanmondi 27, Dhaka", "division": "Dhaka", "district": "Dhaka", "area": "Dhanmondi", "lat": 23.7461, "lng": 90.3742, "price_tier": "budget", "avg_rating": 4.5, "amenities": ["ac"], "is_verified": True},
    {"name": "Pan Pacific Sonargaon", "category": "hotel", "address": "107 Kazi Nazrul Islam Ave, Dhaka", "division": "Dhaka", "district": "Dhaka", "area": "Karwan Bazar", "lat": 23.7519, "lng": 90.3929, "price_tier": "luxury", "avg_rating": 4.7, "amenities": ["parking", "ac", "wifi", "outdoor_seating"], "is_verified": True},
    {"name": "Hatirjheel Lake", "category": "scenic", "address": "Hatirjheel, Dhaka", "division": "Dhaka", "district": "Dhaka", "area": "Hatirjheel", "lat": 23.7712, "lng": 90.4083, "price_tier": "budget", "avg_rating": 4.3, "amenities": [], "is_verified": True},
    {"name": "Lalbagh Fort", "category": "historical", "address": "Lalbagh, Old Dhaka", "division": "Dhaka", "district": "Dhaka", "area": "Lalbagh", "lat": 23.7196, "lng": 90.3885, "price_tier": "budget", "avg_rating": 4.4, "amenities": ["parking"], "is_verified": True},
    {"name": "Skybar Gulshan", "category": "aesthetic", "address": "Gulshan 2, Dhaka", "division": "Dhaka", "district": "Dhaka", "area": "Gulshan", "lat": 23.7936, "lng": 90.4154, "price_tier": "luxury", "avg_rating": 4.6, "amenities": ["ac", "wifi"], "is_verified": True},
    {"name": "Chillox", "category": "restaurant", "address": "Bashundhara City, Dhaka", "division": "Dhaka", "district": "Dhaka", "area": "Panthapath", "lat": 23.7514, "lng": 90.3861, "price_tier": "mid", "avg_rating": 4.1, "amenities": ["ac"], "is_verified": True},
    {"name": "Dhaka Regency Hotel", "category": "hotel", "address": "Airport Road, Dhaka", "division": "Dhaka", "district": "Dhaka", "area": "Nikunja", "lat": 23.8230, "lng": 90.4005, "price_tier": "luxury", "avg_rating": 4.3, "amenities": ["parking", "ac", "wifi"], "is_verified": True},
    {"name": "Mezbaan Restaurant", "category": "restaurant", "address": "Mirpur 10, Dhaka", "division": "Dhaka", "district": "Dhaka", "area": "Mirpur", "lat": 23.8055, "lng": 90.3666, "price_tier": "budget", "avg_rating": 4.0, "amenities": ["ac"], "is_verified": True},
    {"name": "Café Kawa", "category": "cafe", "address": "Uttara Sector 7, Dhaka", "division": "Dhaka", "district": "Dhaka", "area": "Uttara", "lat": 23.8759, "lng": 90.3795, "price_tier": "mid", "avg_rating": 4.4, "amenities": ["ac", "wifi"], "is_verified": True},
]

BUS_STOPS_DATA = [
    {"name": "Mohakhali Bus Stand", "lat": 23.7771, "lng": 90.4040, "division": "Dhaka", "district": "Dhaka"},
    {"name": "Banani Stop", "lat": 23.7937, "lng": 90.4022, "division": "Dhaka", "district": "Dhaka"},
    {"name": "Gulshan 1 Stop", "lat": 23.7808, "lng": 90.4146, "division": "Dhaka", "district": "Dhaka"},
    {"name": "Karwan Bazar Stop", "lat": 23.7519, "lng": 90.3929, "division": "Dhaka", "district": "Dhaka"},
    {"name": "Farmgate Stop", "lat": 23.7580, "lng": 90.3876, "division": "Dhaka", "district": "Dhaka"},
]


async def seed() -> None:
    ensure_bucket_exists()

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == "demo@pinstagram.app"))
        if not result.scalar_one_or_none():
            user = User(
                email="demo@pinstagram.app",
                password_hash=hash_password("demo1234"),
                name="Demo User",
                role="user",
                email_verified=True,
            )
            db.add(user)
            print("Created demo user: demo@pinstagram.app / demo1234")

        for p in PLACES:
            result = await db.execute(select(Place).where(Place.name == p["name"]))
            if not result.scalar_one_or_none():
                place = Place(
                    name=p["name"],
                    category=p["category"],
                    address=p["address"],
                    division=p["division"],
                    district=p["district"],
                    area=p["area"],
                    location=WKTElement(f"POINT({p['lng']} {p['lat']})", srid=4326),
                    price_tier=p["price_tier"],
                    avg_rating=p["avg_rating"],
                    amenities=p.get("amenities", []),
                    is_verified=p["is_verified"],
                )
                db.add(place)
                print(f"  Added place: {p['name']}")

        stop_ids = []
        for s in BUS_STOPS_DATA:
            result = await db.execute(select(BusStop).where(BusStop.name == s["name"]))
            existing = result.scalar_one_or_none()
            if not existing:
                stop = BusStop(name=s["name"], location=WKTElement(f"POINT({s['lng']} {s['lat']})", srid=4326),
                               division=s["division"], district=s["district"])
                db.add(stop)
                await db.flush()
                stop_ids.append(stop.id)
                print(f"  Added bus stop: {s['name']}")
            else:
                stop_ids.append(existing.id)

        if stop_ids and len(stop_ids) >= 2:
            result = await db.execute(select(BusRoute).where(BusRoute.name == "Route 6"))
            if not result.scalar_one_or_none():
                route = BusRoute(name="Route 6", operator="BRTC", stops=stop_ids,
                                 typical_fare=40, typical_duration_min=25)
                db.add(route)
                print("  Added bus route: Route 6")

        for provider, base, per_km, per_min in [("uber", 50, 18, 2), ("pathao", 40, 16, 2), ("obhai", 35, 14, 2)]:
            result = await db.execute(select(TransportFare).where(TransportFare.provider == provider))
            if not result.scalar_one_or_none():
                fare = TransportFare(provider=provider, base_fare=base, per_km=per_km, per_min=per_min)
                db.add(fare)
                print(f"  Added fare: {provider}")

        await db.commit()
        print("\nSeed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
