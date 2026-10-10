import pytest


@pytest.fixture
async def places(make_place):
    await make_place("Cafe Mango", category="cafe", area="Banani")
    await make_place("Banani Book Cafe", category="cafe", area="Banani")
    await make_place("Kacchi Ghor", category="restaurant", area="Dhanmondi")
    await make_place("Lalbagh Fort", category="historical", area="Lalbagh")
    await make_place("Secret Spot", category="cafe", area="Banani", verified=False)


async def _names(client, q, type_="places"):
    resp = await client.get("/api/v1/search", params={"q": q, "type": type_})
    assert resp.status_code == 200, resp.text
    return [p["name"] for p in resp.json()[type_]]


async def test_build_plan_acceptance_cafe_banani(client, places):
    """BUILD_PLAN phase 8: searching "cafe banani" finds the Banani cafes."""
    assert set(await _names(client, "cafe banani")) == {
        "Cafe Mango",
        "Banani Book Cafe",
    }


async def test_prefix_and_category_matching(client, places):
    assert await _names(client, "kac") == ["Kacchi Ghor"]
    # Category and area are indexed too, not just the name.
    assert await _names(client, "restaurant dhanmondi") == ["Kacchi Ghor"]


async def test_typo_tolerance(client, places):
    assert await _names(client, "lalbag fort") == ["Lalbagh Fort"]


async def test_unverified_places_hidden(client, places):
    assert await _names(client, "secret") == []


@pytest.mark.parametrize("q", ["'); DROP TABLE places; --", "a & | ! :* ()", "%%__"])
async def test_hostile_input_is_safe(client, places, q):
    resp = await client.get("/api/v1/search", params={"q": q})
    assert resp.status_code == 200


async def test_hashtags_and_users(client, make_user, make_place, make_post):
    author = await make_user("Nadia Rahman")
    place = await make_place()
    await make_post(
        author, place, hashtags=["kacchi", "foodie"], caption="Best kacchi in town"
    )
    await make_post(author, place, hashtags=["kacchi"], caption="Again")

    body = (await client.get("/api/v1/search", params={"q": "#kac"})).json()
    assert body["hashtags"] == ["kacchi"]
    assert len(body["posts"]) >= 1
    assert await _names(client, "nadia", "users") == ["Nadia Rahman"]


async def test_query_too_short(client):
    assert (await client.get("/api/v1/search", params={"q": "a"})).status_code == 422
