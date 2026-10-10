from tests.conftest import collect_pages


async def test_list_only_verified_places(client, make_place):
    await make_place("Visible")
    await make_place("Hidden", verified=False)
    resp = await client.get("/api/v1/places")
    assert [p["name"] for p in resp.json()["items"]] == ["Visible"]


async def test_place_has_coordinates(client, make_place):
    place = await make_place(lat=23.7190, lng=90.3882)
    detail = (await client.get(f"/api/v1/places/{place.id}")).json()
    assert detail["lat"] == 23.719 and detail["lng"] == 90.3882
    summary = (await client.get("/api/v1/places")).json()["items"][0]
    assert (summary["lat"], summary["lng"]) == (23.719, 90.3882)


async def test_filters(client, make_place):
    await make_place(
        "Cafe A", category="cafe", price_tier="mid", amenities=["wifi", "ac"]
    )
    await make_place(
        "Resto", category="restaurant", price_tier="budget", amenities=["ac"]
    )
    names = lambda r: {p["name"] for p in r.json()["items"]}  # noqa: E731

    assert names(await client.get("/api/v1/places?category=cafe")) == {"Cafe A"}
    assert names(await client.get("/api/v1/places?price_tier=budget")) == {"Resto"}
    assert names(await client.get("/api/v1/places?amenities=wifi,ac")) == {"Cafe A"}
    assert names(await client.get("/api/v1/places?amenities=ac")) == {"Cafe A", "Resto"}
    assert (await client.get("/api/v1/places?category=spaceship")).status_code == 422


async def test_nearby_filter_returns_distance(client, make_place):
    await make_place("Banani", lat=23.7937, lng=90.4066)
    await make_place("Old Dhaka", lat=23.7190, lng=90.3882)  # ~8.5 km away
    resp = await client.get(
        "/api/v1/places",
        params={"near_lat": 23.7937, "near_lng": 90.4066, "radius_m": 2000},
    )
    items = resp.json()["items"]
    assert [p["name"] for p in items] == ["Banani"]
    assert items[0]["distance_m"] == 0


async def test_pagination_has_no_duplicates_or_gaps(client, make_place):
    for i in range(23):
        # Repeated ratings make the (avg_rating, id) tiebreaker matter.
        await make_place(f"P{i}", avg_rating=round(3 + (i % 4) * 0.5, 1))
    items = await collect_pages(client, "/api/v1/places", limit=5)
    assert len(items) == 23
    assert len({p["id"] for p in items}) == 23
    ratings = [p["avg_rating"] for p in items]
    assert ratings == sorted(ratings, reverse=True)


async def test_invalid_cursor_is_400(client):
    assert (await client.get("/api/v1/places?cursor=garbage")).status_code == 400


async def test_get_missing_place_404(client):
    resp = await client.get("/api/v1/places/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_save_place_idempotent(client, make_user, make_place):
    me = await make_user()
    place = await make_place()
    url = f"/api/v1/places/{place.id}/save"
    for _ in range(2):
        assert (await client.post(url, headers=me.headers)).status_code == 204

    detail = (await client.get(f"/api/v1/places/{place.id}", headers=me.headers)).json()
    assert detail["save_count"] == 1
    assert detail["is_saved_by_me"] is True
    anonymous = (await client.get(f"/api/v1/places/{place.id}")).json()
    assert anonymous["is_saved_by_me"] is False

    saved = (
        await client.get("/api/v1/users/me/saved-places", headers=me.headers)
    ).json()
    assert [p["id"] for p in saved["items"]] == [str(place.id)]

    for _ in range(2):
        assert (await client.delete(url, headers=me.headers)).status_code == 204
    detail = (await client.get(f"/api/v1/places/{place.id}")).json()
    assert detail["save_count"] == 0


async def test_save_missing_place_404(client, make_user):
    me = await make_user()
    resp = await client.post(
        "/api/v1/places/00000000-0000-0000-0000-000000000000/save", headers=me.headers
    )
    assert resp.status_code == 404
