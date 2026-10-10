import pytest

BODY = "A genuinely lovely spot with great service and fair prices, would visit again soon."


@pytest.fixture
async def setup(make_user, make_place):
    return (
        await make_user("Reviewer"),
        await make_user("Other"),
        await make_user("Admin", role="admin"),
        await make_place(),
    )


async def _review(client, actor, place, rating=4, body=BODY):
    return await client.post(
        f"/api/v1/places/{place.id}/reviews",
        headers=actor.headers,
        json={"rating": rating, "body": body},
    )


async def _place(client, place):
    return (await client.get(f"/api/v1/places/{place.id}")).json()


async def test_review_lifecycle_updates_rating(client, setup):
    reviewer, other, admin, place = setup
    r1 = (await _review(client, reviewer, place, rating=5)).json()
    r2 = (await _review(client, other, place, rating=2)).json()
    assert r1["status"] == "pending"

    # Pending reviews are hidden and don't count.
    assert (await client.get(f"/api/v1/places/{place.id}/reviews")).json()[
        "items"
    ] == []
    assert (await _place(client, place))["review_count"] == 0

    for r in (r1, r2):
        resp = await client.post(
            f"/api/v1/admin/reviews/{r['id']}/approve", headers=admin.headers
        )
        assert resp.status_code == 204
    p = await _place(client, place)
    assert (p["avg_rating"], p["review_count"]) == (3.5, 2)

    listed = (await client.get(f"/api/v1/places/{place.id}/reviews")).json()["items"]
    assert {r["author_name"] for r in listed} == {"Reviewer", "Other"}

    # Editing sends the review back to moderation and drops it from the average.
    edit = await client.patch(
        f"/api/v1/reviews/{r2['id']}", headers=other.headers, json={"rating": 5}
    )
    assert edit.status_code == 200 and edit.json()["status"] == "pending"
    p = await _place(client, place)
    assert (p["avg_rating"], p["review_count"]) == (5.0, 1)

    assert (
        await client.delete(f"/api/v1/reviews/{r1['id']}", headers=reviewer.headers)
    ).status_code == 204
    p = await _place(client, place)
    assert (p["avg_rating"], p["review_count"]) == (0.0, 0)


async def test_one_review_per_place(client, setup):
    reviewer, _, _, place = setup
    assert (await _review(client, reviewer, place)).status_code == 201
    assert (await _review(client, reviewer, place)).status_code == 409


async def test_review_validation(client, setup):
    reviewer, _, _, place = setup
    assert (await _review(client, reviewer, place, body="too short")).status_code == 422
    assert (await _review(client, reviewer, place, rating=0)).status_code == 422
    assert (await _review(client, reviewer, place, rating=6)).status_code == 422


async def test_cannot_edit_or_delete_others_review(client, setup):
    reviewer, other, _, place = setup
    review = (await _review(client, reviewer, place)).json()
    url = f"/api/v1/reviews/{review['id']}"
    assert (
        await client.patch(url, headers=other.headers, json={"rating": 1})
    ).status_code == 403
    assert (await client.delete(url, headers=other.headers)).status_code == 403


async def test_review_unknown_place_404(client, setup):
    reviewer, *_ = setup
    resp = await client.post(
        "/api/v1/places/00000000-0000-0000-0000-000000000000/reviews",
        headers=reviewer.headers,
        json={"rating": 4, "body": BODY},
    )
    assert resp.status_code == 404
