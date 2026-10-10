import pytest

from tests.conftest import PASSWORD

BODY = "A genuinely lovely spot with great service and fair prices, would visit again soon."


@pytest.fixture
async def admin(make_user):
    return await make_user("Admin", role="admin")


async def test_admin_routes_require_admin(client, make_user):
    user = await make_user()
    for path in [
        "/api/v1/admin/stats",
        "/api/v1/admin/posts/pending",
        "/api/v1/admin/audit-log",
    ]:
        assert (await client.get(path)).status_code == 401
        assert (await client.get(path, headers=user.headers)).status_code == 403


async def test_stats(client, admin, make_user, make_place, make_post):
    author = await make_user()
    place = await make_place()
    await make_post(author, place, status="pending")
    await make_post(author, place)
    stats = (await client.get("/api/v1/admin/stats", headers=admin.headers)).json()
    assert stats["pending_posts"] == 1
    assert stats["total_posts"] == 1
    assert stats["total_users"] == 2


async def test_actions_on_missing_targets_404(client, admin):
    missing = "00000000-0000-0000-0000-000000000000"
    for path in [
        f"/api/v1/admin/posts/{missing}/approve",
        f"/api/v1/admin/reviews/{missing}/approve",
        f"/api/v1/admin/users/{missing}/unban",
        f"/api/v1/admin/places/{missing}/feature",
    ]:
        assert (await client.post(path, headers=admin.headers)).status_code == 404, path


async def test_ban_revokes_sessions_and_is_audited(client, admin, make_user):
    victim = await make_user(email="victim@example.com")
    tokens = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": "victim@example.com", "password": PASSWORD},
        )
    ).json()

    resp = await client.post(
        f"/api/v1/admin/users/{victim.id}/ban",
        headers=admin.headers,
        json={"reason": "spam"},
    )
    assert resp.status_code == 204
    refresh = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh.status_code == 401

    log = (await client.get("/api/v1/admin/audit-log", headers=admin.headers)).json()[
        "items"
    ]
    assert log[0]["action"] == "ban_user"
    assert log[0]["metadata"] == {"reason": "spam"}
    assert log[0]["admin_name"] == "Admin"


async def test_admin_cannot_ban_self(client, admin):
    resp = await client.post(
        f"/api/v1/admin/users/{admin.id}/ban", headers=admin.headers
    )
    assert resp.status_code == 400


async def test_promote_validates_role(client, admin, make_user):
    user = await make_user()
    bad = await client.post(
        f"/api/v1/admin/users/{user.id}/promote",
        headers=admin.headers,
        json={"role": "god"},
    )
    assert bad.status_code == 422
    ok = await client.post(
        f"/api/v1/admin/users/{user.id}/promote",
        headers=admin.headers,
        json={"role": "creator"},
    )
    assert ok.status_code == 204
    users = (await client.get("/api/v1/admin/users", headers=admin.headers)).json()[
        "items"
    ]
    assert {u["id"]: u["role"] for u in users}[str(user.id)] == "creator"


async def test_report_remove_content_unpublishes_review(
    client, admin, make_user, make_place
):
    author, reporter = await make_user(), await make_user()
    place = await make_place()
    review = (
        await client.post(
            f"/api/v1/places/{place.id}/reviews",
            headers=author.headers,
            json={"rating": 1, "body": BODY},
        )
    ).json()
    await client.post(
        f"/api/v1/admin/reviews/{review['id']}/approve", headers=admin.headers
    )
    assert (await client.get(f"/api/v1/places/{place.id}")).json()["review_count"] == 1

    report = (
        await client.post(
            "/api/v1/reports",
            headers=reporter.headers,
            json={
                "target_type": "review",
                "target_id": review["id"],
                "reason": "fake_review",
            },
        )
    ).json()
    open_reports = (
        await client.get("/api/v1/admin/reports", headers=admin.headers)
    ).json()
    assert [r["id"] for r in open_reports["items"]] == [report["id"]]

    resp = await client.post(
        f"/api/v1/admin/reports/{report['id']}/resolve",
        headers=admin.headers,
        json={"action": "remove_content"},
    )
    assert resp.status_code == 204
    p = (await client.get(f"/api/v1/places/{place.id}")).json()
    assert (p["review_count"], p["avg_rating"]) == (0, 0.0)
    assert (await client.get("/api/v1/admin/reports", headers=admin.headers)).json()[
        "items"
    ] == []


async def test_report_ban_user_bans_author(
    client, admin, make_user, make_place, make_post
):
    author, reporter = await make_user(email="bad@example.com"), await make_user()
    post = await make_post(author, await make_place())
    report = (
        await client.post(
            "/api/v1/reports",
            headers=reporter.headers,
            json={"target_type": "post", "target_id": str(post.id), "reason": "hate"},
        )
    ).json()
    await client.post(
        f"/api/v1/admin/reports/{report['id']}/resolve",
        headers=admin.headers,
        json={"action": "ban_user"},
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": "bad@example.com", "password": PASSWORD}
    )
    assert login.status_code == 403


async def test_create_place(client, admin):
    resp = await client.post(
        "/api/v1/admin/places",
        headers=admin.headers,
        json={
            "name": "New Cafe",
            "category": "cafe",
            "address": "Road 1, Gulshan",
            "lat": 23.79,
            "lng": 90.41,
        },
    )
    assert resp.status_code == 201
    place = resp.json()
    assert place["is_verified"] is True and place["lat"] == 23.79
    public = (await client.get("/api/v1/places")).json()["items"]
    assert [p["name"] for p in public] == ["New Cafe"]


STOPS_CSV = """name,lat,lng,district
Abdullahpur,23.8794,90.4006,Dhaka
Airport,23.8513,90.4086,Dhaka
Banani,23.7946,90.4019,Dhaka
"""

ROUTES_CSV = """name,operator,typical_fare,typical_duration_min,stops
Airport Express,BRTC,40,45,Abdullahpur|Airport|Banani
"""


async def _upload(client, admin, kind: str, content: str):
    return await client.post(
        f"/api/v1/admin/transport/import/{kind}",
        headers=admin.headers,
        files={"file": (f"{kind}.csv", content.encode(), "text/csv")},
    )


async def test_csv_transport_import(client, admin, make_place):
    resp = await _upload(client, admin, "bus-stops", STOPS_CSV)
    assert resp.json() == {"created": 3, "updated": 0}
    # Re-importing upserts by name instead of duplicating.
    assert (await _upload(client, admin, "bus-stops", STOPS_CSV)).json() == {
        "created": 0,
        "updated": 3,
    }

    assert (await _upload(client, admin, "bus-routes", ROUTES_CSV)).json() == {
        "created": 1,
        "updated": 0,
    }
    summary = (
        await client.get("/api/v1/admin/transport/summary", headers=admin.headers)
    ).json()
    assert (summary["bus_stops"], summary["bus_routes"]) == (3, 1)

    # The imported route is immediately usable for directions.
    place = await make_place(lat=23.7948, lng=90.4020)
    directions = (
        await client.get(
            f"/api/v1/places/{place.id}/directions",
            params={"from_lat": 23.8795, "from_lng": 90.4007},
        )
    ).json()
    bus = next(o for o in directions["options"] if o["mode"] == "bus")
    assert bus["steps"][1]["route_name"] == "Airport Express"


async def test_csv_import_reports_all_errors(client, admin):
    bad = "name,lat,lng\nOk,23.8,90.4\nBad lat,999,90.4\n,23.8,90.4\n"
    resp = await _upload(client, admin, "bus-stops", bad)
    assert resp.status_code == 422
    assert [e["line"] for e in resp.json()["detail"]["errors"]] == [3, 4]
    # All-or-nothing: the valid row was not imported either.
    summary = (
        await client.get("/api/v1/admin/transport/summary", headers=admin.headers)
    ).json()
    assert summary["bus_stops"] == 0

    missing_col = await _upload(client, admin, "bus-stops", "name,lat\nX,1\n")
    assert missing_col.status_code == 422

    unknown_stop = await _upload(
        client,
        admin,
        "bus-routes",
        "name,operator,typical_fare,typical_duration_min,stops\nR,,10,10,Nowhere|Elsewhere\n",
    )
    assert unknown_stop.status_code == 422
    assert "Unknown stops" in unknown_stop.json()["detail"]["errors"][0]["error"]
