"""
Usage: python -m app.scripts.seed_dev

Seeds a realistic local dataset: Dhaka places, bus stops/routes along the main
corridors, rail stations and timetables, ride-hail fares, demo users with posts,
likes, comments, follows and reviews. Idempotent: rows are matched by natural
keys (email, name), so re-running only fills in what's missing.

Landmarks are real public places with approximate coordinates; cafes,
restaurants and hotels are fictional so no real business gets fake reviews.
Images are placeholders from picsum.photos.
"""

import asyncio
import random
import secrets
from datetime import UTC, datetime, time, timedelta

from geoalchemy2.elements import WKTElement
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.place import Place
from app.models.post import Post, PostComment, PostLike
from app.models.review import Review
from app.models.social import Follow, SavedPlace
from app.models.transport import (
    BusRoute,
    BusStop,
    TrainSchedule,
    TrainStation,
    TransportFare,
)
from app.models.user import User
from app.services.reviews_service import recompute_place_rating
from app.services.uploads_service import ensure_bucket_exists

rng = random.Random(42)  # deterministic demo data


def img(seed: str, size: int = 1080) -> str:
    return f"https://picsum.photos/seed/{seed}/{size}/{size}"


def pt(lat: float, lng: float) -> WKTElement:
    return WKTElement(f"POINT({lng} {lat})", srid=4326)


# (name, category, area, lat, lng, price_tier, amenities, description)
PLACES = [
    (
        "Lalbagh Fort",
        "historical",
        "Lalbagh",
        23.7190,
        90.3882,
        "budget",
        ["parking"],
        "Unfinished 17th-century Mughal fort complex with gardens, a mosque and the tomb of Pari Bibi.",
    ),
    (
        "Ahsan Manzil",
        "historical",
        "Kumartuli",
        23.7086,
        90.4060,
        "budget",
        [],
        "The Pink Palace on the Buriganga, former seat of the Dhaka Nawabs, now a museum.",
    ),
    (
        "Star Mosque",
        "historical",
        "Armanitola",
        23.7158,
        90.4006,
        "budget",
        [],
        "18th-century mosque covered in blue star mosaics made from Japanese and English china.",
    ),
    (
        "Dhakeshwari Temple",
        "historical",
        "Palashi",
        23.7231,
        90.3867,
        "budget",
        [],
        "The national temple of Bangladesh, said to date back to the 12th century.",
    ),
    (
        "National Parliament House",
        "aesthetic",
        "Sher-e-Bangla Nagar",
        23.7625,
        90.3785,
        "budget",
        ["parking"],
        "Louis Kahn's concrete masterpiece. Best photographed at golden hour from Crescent Lake.",
    ),
    (
        "Hatirjheel Lake",
        "scenic",
        "Hatirjheel",
        23.7712,
        90.4083,
        "budget",
        [],
        "Lakefront promenade with bridges, water taxis and evening light shows.",
    ),
    (
        "Dhanmondi Lake",
        "scenic",
        "Dhanmondi",
        23.7465,
        90.3775,
        "budget",
        ["outdoor_seating"],
        "Tree-lined lake walk with food stalls, paddle boats and Rabindra Sarobar.",
    ),
    (
        "Ramna Park",
        "scenic",
        "Ramna",
        23.7380,
        90.4010,
        "budget",
        [],
        "The oldest park in Dhaka; the centre of Pohela Boishakh celebrations.",
    ),
    (
        "National Botanical Garden",
        "scenic",
        "Mirpur",
        23.8160,
        90.3460,
        "budget",
        ["parking"],
        "84 hectares of greenhouses, lotus ponds and over 1,000 plant species.",
    ),
    (
        "Gulshan Lake Park",
        "scenic",
        "Gulshan",
        23.7980,
        90.4180,
        "budget",
        ["outdoor_seating"],
        "Quiet lakeside park popular for morning jogs and evening walks.",
    ),
    (
        "Cafe Mango",
        "cafe",
        "Banani",
        23.7937,
        90.4066,
        "mid",
        ["ac", "wifi"],
        "Bright corner cafe known for mango cold brew and a sunny window bar.",
    ),
    (
        "Banani Book Cafe",
        "cafe",
        "Banani",
        23.7920,
        90.4040,
        "mid",
        ["ac", "wifi"],
        "Second-hand books, board games and a strong cardamom latte.",
    ),
    (
        "Uttara Bean Co.",
        "cafe",
        "Uttara",
        23.8759,
        90.3795,
        "mid",
        ["ac", "wifi", "parking"],
        "Specialty coffee roastery with single-origin pour-overs.",
    ),
    (
        "Tong Tea Corner",
        "cafe",
        "Karwan Bazar",
        23.7515,
        90.3925,
        "budget",
        ["outdoor_seating"],
        "Classic street-side tea stall: malai cha, singara and adda till late.",
    ),
    (
        "Kacchi Ghor",
        "restaurant",
        "Dhanmondi",
        23.7461,
        90.3742,
        "budget",
        ["ac"],
        "Slow-cooked mutton kacchi biryani served from giant handi pots.",
    ),
    (
        "Old Dhaka Biryani House",
        "restaurant",
        "Nazira Bazar",
        23.7203,
        90.4030,
        "budget",
        [],
        "Narrow lane institution for haji-style biryani and borhani.",
    ),
    (
        "Mezban Bari",
        "restaurant",
        "Mirpur",
        23.8055,
        90.3666,
        "budget",
        ["ac"],
        "Chittagonian mezban beef and kala bhuna, family-style.",
    ),
    (
        "Lakeview Rooftop",
        "aesthetic",
        "Gulshan",
        23.7936,
        90.4154,
        "luxury",
        ["ac", "wifi", "outdoor_seating"],
        "Rooftop lounge over Gulshan Lake with sunset views and mocktails.",
    ),
    (
        "Hotel Shapla Grand",
        "hotel",
        "Karwan Bazar",
        23.7519,
        90.3929,
        "luxury",
        ["parking", "ac", "wifi"],
        "Business hotel with a pool, five minutes from Karwan Bazar metro.",
    ),
    (
        "Airport Garden Inn",
        "hotel",
        "Nikunja",
        23.8230,
        90.4170,
        "mid",
        ["parking", "ac", "wifi"],
        "Comfortable stopover hotel with free airport shuttle.",
    ),
]

BUS_STOPS = {
    "Abdullahpur": (23.8794, 90.4006),
    "House Building": (23.8737, 90.4004),
    "Airport": (23.8513, 90.4086),
    "Khilkhet": (23.8296, 90.4196),
    "Kuril Bishwa Road": (23.8167, 90.4210),
    "Banani": (23.7946, 90.4019),
    "Mohakhali": (23.7781, 90.3982),
    "Jahangir Gate": (23.7746, 90.3906),
    "Bijoy Sarani": (23.7656, 90.3889),
    "Farmgate": (23.7577, 90.3897),
    "Karwan Bazar": (23.7509, 90.3934),
    "Bangla Motor": (23.7466, 90.3951),
    "Shahbag": (23.7385, 90.3960),
    "Press Club": (23.7297, 90.4049),
    "Gulistan": (23.7234, 90.4113),
    "Mirpur 10": (23.8069, 90.3687),
    "Mirpur 1": (23.7957, 90.3537),
    "Shyamoli": (23.7743, 90.3653),
    "Asad Gate": (23.7600, 90.3735),
    "Dhanmondi 27": (23.7563, 90.3745),
    "Science Lab": (23.7390, 90.3830),
    "Nilkhet": (23.7330, 90.3858),
    "Azimpur": (23.7270, 90.3864),
    "Lalbagh Chowrasta": (23.7184, 90.3870),
    "Gulshan 1": (23.7808, 90.4167),
    "Gulshan 2": (23.7925, 90.4148),
    "Notun Bazar": (23.7980, 90.4237),
    "Badda": (23.7807, 90.4260),
    "Rampura": (23.7612, 90.4210),
    "Malibagh": (23.7495, 90.4130),
    "Moghbazar": (23.7490, 90.4035),
    "Police Plaza": (23.7742, 90.4127),
    "Agargaon": (23.7779, 90.3800),
}

# (name, operator, fare, minutes, stops in order)
BUS_ROUTES = [
    (
        "Airport Road Express",
        "BRTC",
        60,
        95,
        [
            "Abdullahpur",
            "House Building",
            "Airport",
            "Khilkhet",
            "Kuril Bishwa Road",
            "Banani",
            "Mohakhali",
            "Jahangir Gate",
            "Bijoy Sarani",
            "Farmgate",
            "Karwan Bazar",
            "Bangla Motor",
            "Shahbag",
            "Press Club",
            "Gulistan",
        ],
    ),
    (
        "Mirpur Road Link",
        "Bikolpo",
        35,
        65,
        [
            "Mirpur 10",
            "Mirpur 1",
            "Shyamoli",
            "Asad Gate",
            "Dhanmondi 27",
            "Science Lab",
            "Nilkhet",
            "Azimpur",
            "Lalbagh Chowrasta",
        ],
    ),
    (
        "Mirpur–Motijheel",
        "Shikhor",
        40,
        70,
        [
            "Mirpur 10",
            "Agargaon",
            "Bijoy Sarani",
            "Farmgate",
            "Karwan Bazar",
            "Shahbag",
            "Press Club",
            "Gulistan",
        ],
    ),
    (
        "Gulshan Chaka",
        "Dhaka Chaka",
        20,
        25,
        ["Gulshan 1", "Gulshan 2", "Notun Bazar", "Banani"],
    ),
    (
        "Progoti Sarani Line",
        "Turag",
        45,
        70,
        [
            "Abdullahpur",
            "Kuril Bishwa Road",
            "Notun Bazar",
            "Badda",
            "Rampura",
            "Malibagh",
            "Moghbazar",
            "Bangla Motor",
        ],
    ),
    (
        "Hatirjheel Circular",
        "Hatirjheel Transit",
        25,
        30,
        [
            "Police Plaza",
            "Gulshan 1",
            "Mohakhali",
            "Moghbazar",
            "Rampura",
            "Police Plaza",
        ],
    ),
]

TRAIN_STATIONS = {
    "Kamalapur": (23.7322, 90.4260),
    "Tejgaon": (23.7621, 90.3955),
    "Banani Rail Station": (23.7953, 90.4060),
    "Dhaka Airport Station": (23.8510, 90.4080),
}

# (from, to, departures, minutes, fare)
TRAIN_SCHEDULES = [
    (
        "Kamalapur",
        "Dhaka Airport Station",
        ["06:40", "09:15", "13:00", "17:30", "21:10"],
        35,
        45,
    ),
    (
        "Dhaka Airport Station",
        "Kamalapur",
        ["07:50", "10:30", "14:20", "18:45", "22:15"],
        35,
        45,
    ),
    ("Tejgaon", "Dhaka Airport Station", ["06:52", "09:27", "13:12", "17:42"], 22, 30),
    ("Dhaka Airport Station", "Tejgaon", ["08:15", "10:55", "14:45", "19:10"], 22, 30),
    ("Kamalapur", "Banani Rail Station", ["06:40", "13:00", "17:30"], 25, 30),
    ("Banani Rail Station", "Kamalapur", ["08:05", "14:35", "19:00"], 25, 30),
]

FARES = [("uber", 50, 18, 2), ("pathao", 40, 16, 2), ("obhai", 35, 14, 2)]

USERS = [
    (
        "demo@pinstagram.app",
        "Demo User",
        "Exploring Dhaka one cup of cha at a time.",
        "user",
    ),
    (
        "nadia@pinstagram.app",
        "Nadia Rahman",
        "Food photographer. Kacchi critic.",
        "creator",
    ),
    ("arif@pinstagram.app", "Arif Hossain", "Heritage walks around Old Dhaka.", "user"),
    ("tania@pinstagram.app", "Tania Akter", "Cafe hopper | Banani & Gulshan", "user"),
    ("rafi@pinstagram.app", "Rafi Chowdhury", "Weekend cyclist, lake chaser.", "user"),
    ("admin@pinstagram.app", "Pinstagram Admin", None, "admin"),
]
DEMO_PASSWORD = "demo1234"

CAPTIONS = {
    "historical": [
        ("Golden hour at the fort walls", ["heritage", "olddhaka"]),
        ("Every arch tells a story", ["architecture", "history"]),
        ("Worth the early start before the crowds", ["weekend", "heritage"]),
    ],
    "scenic": [
        ("Evening breeze by the water", ["sunset", "dhaka"]),
        ("Found my new morning walk spot", ["green", "weekend"]),
        ("Monsoon skies over the lake", ["monsoon", "lake"]),
    ],
    "cafe": [
        ("Best cold brew in the area, no contest", ["coffee", "cafehopping"]),
        ("Rainy day, warm latte", ["coffee", "monsoon"]),
        ("Work-from-cafe Wednesday", ["wfh", "coffee"]),
    ],
    "restaurant": [
        ("The kacchi here is unreal", ["kacchi", "foodie"]),
        ("Came for lunch, stayed for dessert", ["foodie", "dhakafood"]),
        ("Borhani + biryani = perfect Friday", ["biryani", "foodie"]),
    ],
    "aesthetic": [
        ("Concrete and light", ["architecture", "aesthetic"]),
        ("Views for days", ["sunset", "rooftop"]),
    ],
    "hotel": [
        ("Staycation mode on", ["staycation", "pool"]),
        ("Breakfast spread was huge", ["hotel", "breakfast"]),
    ],
}

REVIEW_BODIES = [
    "Went on a weekday afternoon and it was calm and clean. Staff were friendly and helpful, would come back.",
    "Busy on Friday evening, so come early. The atmosphere makes up for the wait and prices are fair.",
    "Lovely spot for photos, especially around sunset. Parking is a hassle so take a rickshaw from the main road.",
    "Decent overall. A few things could be better maintained but it is still worth a visit if you are nearby.",
    "One of my favourite places in Dhaka. Great for taking visiting friends and family, never disappoints.",
]


def _password_for(email: str, role: str, admin_password: str, production: bool) -> str:
    """Only the shared demo login is public. On a public deployment the other
    seeded accounts get unguessable passwords."""
    if role == "admin":
        return admin_password
    if email == settings.DEMO_USER_EMAIL or not production:
        return DEMO_PASSWORD
    return secrets.token_urlsafe(24)


async def seed() -> None:
    production = settings.ENV == "production"
    if production and not settings.ADMIN_PASSWORD:
        raise SystemExit("Set ADMIN_PASSWORD before seeding a public deployment.")
    admin_password = settings.ADMIN_PASSWORD or "admin1234"
    try:
        ensure_bucket_exists()
    except Exception as exc:  # storage is optional for browsing seeded data
        print(f"  (skipping bucket setup: {exc})")

    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        users: dict[str, User] = {}
        for email, name, bio, role in USERS:
            user = (
                await db.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
            if not user:
                user = User(
                    email=email,
                    password_hash=hash_password(
                        _password_for(email, role, admin_password, production)
                    ),
                    name=name,
                    bio=bio,
                    role=role,
                    location="Dhaka",
                    email_verified=True,
                    is_verified=role == "creator",
                    avatar_url=img(f"avatar-{email}", 256) if role != "admin" else None,
                )
                db.add(user)
                print(f"  user  {email}")
            users[email] = user
        await db.flush()

        places: dict[str, Place] = {}
        for name, cat, area, lat, lng, tier, amenities, desc in PLACES:
            place = (
                await db.execute(select(Place).where(Place.name == name))
            ).scalar_one_or_none()
            if not place:
                place = Place(
                    name=name,
                    category=cat,
                    description=desc,
                    address=f"{area}, Dhaka",
                    division="Dhaka",
                    district="Dhaka",
                    area=area,
                    location=pt(lat, lng),
                    price_tier=tier,
                    amenities=amenities,
                    cover_photo_url=img(name.lower().replace(" ", "-")),
                    is_verified=True,
                    is_featured=cat in ("historical", "scenic") and rng.random() < 0.4,
                )
                db.add(place)
                print(f"  place {name}")
            places[name] = place
        await db.flush()

        stops: dict[str, BusStop] = {}
        for name, (lat, lng) in BUS_STOPS.items():
            stop = (
                await db.execute(select(BusStop).where(BusStop.name == name))
            ).scalar_one_or_none()
            if not stop:
                stop = BusStop(
                    name=name, location=pt(lat, lng), division="Dhaka", district="Dhaka"
                )
                db.add(stop)
            stops[name] = stop
        await db.flush()

        for name, operator, fare, minutes, stop_names in BUS_ROUTES:
            if not (
                await db.execute(select(BusRoute).where(BusRoute.name == name))
            ).scalar_one_or_none():
                db.add(
                    BusRoute(
                        name=name,
                        operator=operator,
                        stops=[str(stops[s].id) for s in stop_names],
                        typical_fare=fare,
                        typical_duration_min=minutes,
                    )
                )
                print(f"  bus   {name}")

        stations: dict[str, TrainStation] = {}
        for name, (lat, lng) in TRAIN_STATIONS.items():
            st = (
                await db.execute(select(TrainStation).where(TrainStation.name == name))
            ).scalar_one_or_none()
            if not st:
                st = TrainStation(name=name, location=pt(lat, lng), division="Dhaka")
                db.add(st)
            stations[name] = st
        await db.flush()

        if not (await db.execute(select(TrainSchedule).limit(1))).scalar_one_or_none():
            for frm, to, departures, minutes, fare in TRAIN_SCHEDULES:
                for dep in departures:
                    h, m = map(int, dep.split(":"))
                    db.add(
                        TrainSchedule(
                            from_station_id=stations[frm].id,
                            to_station_id=stations[to].id,
                            departure_time=time(h, m),
                            duration_min=minutes,
                            fare=fare,
                            days_of_week=[1, 2, 3, 4, 5, 6, 7],
                        )
                    )
            print("  train schedules")

        for provider, base, per_km, per_min in FARES:
            if not (
                await db.execute(
                    select(TransportFare).where(TransportFare.provider == provider)
                )
            ).scalar_one_or_none():
                db.add(
                    TransportFare(
                        provider=provider,
                        base_fare=base,
                        per_km=per_km,
                        per_min=per_min,
                    )
                )

        # Social graph and content only on first run.
        if (await db.execute(select(Post).limit(1))).scalar_one_or_none() is None:
            people = [u for e, u in users.items() if u.role != "admin"]
            for a in people:
                for b in people:
                    if a is not b and rng.random() < 0.6:
                        db.add(
                            Follow(
                                follower_id=a.id,
                                followee_id=b.id,
                                created_at=now - timedelta(days=rng.randint(5, 60)),
                            )
                        )

            posts: list[Post] = []
            for i, place in enumerate(places.values()):
                for j in range(rng.randint(1, 3)):
                    author = rng.choice(people)
                    caption, tags = rng.choice(CAPTIONS[place.category])
                    created = now - timedelta(hours=rng.randint(1, 24 * 20))
                    post = Post(
                        user_id=author.id,
                        place_id=place.id,
                        media_url=img(f"post-{i}-{j}"),
                        media_type="image",
                        caption=caption,
                        hashtags=tags,
                        price_mentioned=rng.choice([None, 120, 250, 450])
                        if place.category in ("cafe", "restaurant")
                        else None,
                        rating=rng.randint(4, 5),
                        status="published",
                        created_at=created,
                        updated_at=created,
                    )
                    db.add(post)
                    posts.append(post)
            # One post waiting in the moderation queue for the admin demo.
            db.add(
                Post(
                    user_id=users["tania@pinstagram.app"].id,
                    place_id=places["Cafe Mango"].id,
                    media_url=img("pending-1"),
                    media_type="image",
                    caption="New seasonal menu!",
                    hashtags=["coffee"],
                    status="pending",
                )
            )
            await db.flush()

            for post in posts:
                likers = rng.sample(people, rng.randint(0, len(people)))
                for u in likers:
                    db.add(
                        PostLike(
                            user_id=u.id,
                            post_id=post.id,
                            created_at=post.created_at + timedelta(hours=1),
                        )
                    )
                post.like_count = len(likers)
                commenters = rng.sample(people, rng.randint(0, 2))
                for u in commenters:
                    db.add(
                        PostComment(
                            post_id=post.id,
                            user_id=u.id,
                            body=rng.choice(
                                [
                                    "Adding this to my list!",
                                    "Love this spot",
                                    "How was the crowd?",
                                    "Beautiful shot",
                                ]
                            ),
                            created_at=post.created_at + timedelta(hours=2),
                        )
                    )
                post.comment_count = len(commenters)

            for place in places.values():
                for u in rng.sample(people, rng.randint(2, 4)):
                    db.add(
                        Review(
                            user_id=u.id,
                            place_id=place.id,
                            rating=rng.choice([3, 4, 4, 5, 5]),
                            body=rng.choice(REVIEW_BODIES),
                            status="published",
                            price_paid=rng.choice([None, 200, 500])
                            if place.category in ("cafe", "restaurant")
                            else None,
                        )
                    )
            await db.flush()
            for place in places.values():
                await recompute_place_rating(db, place.id)

            demo = users["demo@pinstagram.app"]
            for name in ("Lalbagh Fort", "Cafe Mango", "Hatirjheel Lake"):
                db.add(
                    SavedPlace(
                        user_id=demo.id, place_id=places[name].id, created_at=now
                    )
                )
                places[name].save_count += 1
            print(f"  {len(posts)} posts, likes, comments, reviews")

        await db.commit()

    admin_hint = "<ADMIN_PASSWORD>" if settings.ADMIN_PASSWORD else "admin1234"
    print(
        f"\nSeed complete. Log in as demo@pinstagram.app / {DEMO_PASSWORD} "
        f"(admin: admin@pinstagram.app / {admin_hint})"
    )


if __name__ == "__main__":
    asyncio.run(seed())
