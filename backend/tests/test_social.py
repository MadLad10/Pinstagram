async def test_followers_and_following_are_different_lists(client, make_user):
    """Regression: /following used to return the followers list."""
    alice, bob, carol = (
        await make_user("Alice"),
        await make_user("Bob"),
        await make_user("Carol"),
    )
    await client.post(f"/api/v1/users/{bob.id}/follow", headers=alice.headers)
    await client.post(f"/api/v1/users/{alice.id}/follow", headers=carol.headers)

    followers = (await client.get(f"/api/v1/users/{alice.id}/followers")).json()[
        "items"
    ]
    following = (await client.get(f"/api/v1/users/{alice.id}/following")).json()[
        "items"
    ]
    assert [u["name"] for u in followers] == ["Carol"]
    assert [u["name"] for u in following] == ["Bob"]


async def test_follow_counts_and_flags(client, make_user):
    alice, bob = await make_user("Alice"), await make_user("Bob")
    for _ in range(2):  # idempotent
        assert (
            await client.post(f"/api/v1/users/{bob.id}/follow", headers=alice.headers)
        ).status_code == 204

    profile = (
        await client.get(f"/api/v1/users/{bob.id}", headers=alice.headers)
    ).json()
    assert profile["follower_count"] == 1 and profile["is_following"] is True

    followers = (
        await client.get(f"/api/v1/users/{bob.id}/followers", headers=bob.headers)
    ).json()
    assert (
        followers["items"][0]["is_following"] is False
    )  # Bob doesn't follow Alice back

    await client.delete(f"/api/v1/users/{bob.id}/follow", headers=alice.headers)
    profile = (
        await client.get(f"/api/v1/users/{bob.id}", headers=alice.headers)
    ).json()
    assert profile["follower_count"] == 0 and profile["is_following"] is False

    notes = (await client.get("/api/v1/notifications", headers=bob.headers)).json()
    assert [n["type"] for n in notes["items"]] == [
        "follow"
    ]  # only one despite double-follow


async def test_cannot_follow_self_or_missing_user(client, make_user):
    alice = await make_user()
    assert (
        await client.post(f"/api/v1/users/{alice.id}/follow", headers=alice.headers)
    ).status_code == 400
    missing = "/api/v1/users/00000000-0000-0000-0000-000000000000/follow"
    assert (await client.post(missing, headers=alice.headers)).status_code == 404


async def test_block_removes_follows_and_prevents_refollow(client, make_user):
    alice, bob = await make_user("Alice"), await make_user("Bob")
    await client.post(f"/api/v1/users/{bob.id}/follow", headers=alice.headers)
    await client.post(f"/api/v1/users/{alice.id}/follow", headers=bob.headers)

    assert (
        await client.post(f"/api/v1/users/{bob.id}/block", headers=alice.headers)
    ).status_code == 204
    assert (await client.get(f"/api/v1/users/{alice.id}/followers")).json()[
        "items"
    ] == []
    assert (await client.get(f"/api/v1/users/{alice.id}/following")).json()[
        "items"
    ] == []
    assert (
        await client.post(f"/api/v1/users/{alice.id}/follow", headers=bob.headers)
    ).status_code == 403


async def test_private_profile(client, make_user):
    private = await make_user("Private", is_private=True)
    stranger, friend = await make_user("Stranger"), await make_user("Friend")
    await client.post(f"/api/v1/users/{private.id}/follow", headers=friend.headers)

    assert (
        await client.get(f"/api/v1/users/{private.id}", headers=stranger.headers)
    ).status_code == 403
    assert (
        await client.get(f"/api/v1/users/{private.id}/posts", headers=stranger.headers)
    ).status_code == 403
    assert (
        await client.get(f"/api/v1/users/{private.id}", headers=friend.headers)
    ).status_code == 200
    assert (
        await client.get(f"/api/v1/users/{private.id}", headers=private.headers)
    ).status_code == 200


async def test_update_profile(client, make_user):
    me = await make_user("Old")
    resp = await client.patch(
        "/api/v1/users/me", headers=me.headers, json={"name": "New", "bio": "hi"}
    )
    assert resp.status_code == 200 and resp.json()["name"] == "New"
    assert (
        await client.patch("/api/v1/users/me", headers=me.headers, json={"name": ""})
    ).status_code == 422


async def test_notifications_mark_read(client, make_user):
    alice, bob = await make_user("Alice"), await make_user("Bob")
    await client.post(f"/api/v1/users/{bob.id}/follow", headers=alice.headers)
    assert (await client.get("/api/v1/notifications", headers=bob.headers)).json()[
        "unread_count"
    ] == 1
    assert (
        await client.post("/api/v1/notifications/read-all", headers=bob.headers)
    ).status_code == 204
    body = (await client.get("/api/v1/notifications", headers=bob.headers)).json()
    assert body["unread_count"] == 0 and body["items"][0]["is_read"] is True


async def test_report_validation(client, make_user):
    me = await make_user()
    ok = await client.post(
        "/api/v1/reports",
        headers=me.headers,
        json={"target_type": "user", "target_id": str(me.id), "reason": "spam"},
    )
    assert ok.status_code == 201
    bad = await client.post(
        "/api/v1/reports",
        headers=me.headers,
        json={
            "target_type": "user",
            "target_id": str(me.id),
            "reason": "i-dont-like-it",
        },
    )
    assert bad.status_code == 422
