"""Review summaries: grounding rules, caching and regeneration triggers.
The LLM is a FakeLLM whose replies are scripted per test."""

import json

import pytest
from sqlalchemy import func, select, update

from app.ai.types import LLMError
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.llm_call import LLMCall
from app.models.review import Review
from app.models.review_summary import ReviewSummary
from app.services import summary_service
from app.services.summary_service import SummaryError, ground, supported

REVIEWS = {
    "R1": "Wifi is fast and they don't mind if you stay a few hours.",
    "R2": "Coffee is good but expensive, around 350 taka for a cold brew.",
    "R3": "Gets loud after lunch with office crowds.",
}


def _reply(**sections) -> str:
    return json.dumps(
        {
            key: [{"point": p, "reviews": refs} for p, refs in sections.get(key, [])]
            for key in ("pros", "cons", "best_for")
        }
    )


# ------------------------------------------------------------------ grounding


def test_ground_keeps_cited_supported_points():
    out, dropped = ground(
        _reply(
            pros=[("Fast wifi, no pressure to leave", ["R1"])],
            cons=[
                ("Cold brew costs around 350 taka", ["R2"]),
                ("Loud after lunch", ["R3"]),
            ],
            best_for=[("Working for a few hours", ["R1"])],
        ),
        REVIEWS,
    )
    assert dropped == 0
    assert out["pros"] == [
        {"text": "Fast wifi, no pressure to leave", "labels": ["R1"]}
    ]
    assert [p["text"] for p in out["cons"]] == [
        "Cold brew costs around 350 taka",
        "Loud after lunch",
    ]
    assert out["best_for"][0]["labels"] == ["R1"]


@pytest.mark.parametrize(
    ("point", "refs", "why"),
    [
        ("Fast wifi", [], "no citation"),
        ("Fast wifi", ["R9"], "cites a review that wasn't shown"),
        ("Cold brew costs 500 taka", ["R2"], "number not in the cited review"),
        ("Free parking for customers", ["R1"], "cited review doesn't mention it"),
        ("Great place, worth it", ["R1"], "nothing specific to check"),
        ("Fast wifi " * 30, ["R1"], "too long"),
    ],
)
def test_ground_drops_ungrounded_points(point, refs, why):
    out, dropped = ground(_reply(pros=[(point, refs)]), REVIEWS)
    assert out["pros"] == [], why
    assert dropped == 1


def test_ground_tolerates_model_quirks():
    raw = (
        "```json\n"
        + json.dumps(
            {
                "pros": [
                    {"point": "Fast wifi", "reviews": ["r1", "[R1]", 1]},
                    {"point": "fast   wifi", "reviews": ["R1"]},  # duplicate
                    "Uncited bare string",
                ],
                "cons": None,
            }
        )
        + "\n```"
    )
    out, dropped = ground(raw, REVIEWS)
    assert out == {
        "pros": [{"text": "Fast wifi", "labels": ["R1"]}],
        "cons": [],
        "best_for": [],
    }
    assert dropped == 1


def test_ground_caps_points_per_section():
    out, _ = ground(
        _reply(pros=[(f"Fast wifi {i}", ["R1"]) for i in range(8)]),
        {"R1": "Fast wifi " + " ".join(str(i) for i in range(8))},
    )
    assert len(out["pros"]) == summary_service.MAX_POINTS


def test_ground_rejects_non_json():
    with pytest.raises(SummaryError):
        ground("Here is a summary: it's great!", REVIEWS)


def test_supported_matches_word_forms():
    assert supported("Pricey drinks", ["Drinks are pricey."])
    assert supported("Good for photography", ["Lovely spot for photos at sunset."])
    assert not supported("Has a swimming pool", ["Lovely spot for photos."])


# ---------------------------------------------------------------- end to end


@pytest.fixture
async def cafe(make_place, make_user, make_review):
    place = await make_place("Cafe Mango")
    users = [await make_user(f"U{i}") for i in range(6)]
    reviews = [
        await make_review(users[0], place, REVIEWS["R1"], rating=5),
        await make_review(users[1], place, REVIEWS["R2"], rating=3),
        await make_review(users[2], place, REVIEWS["R3"], rating=4),
    ]
    pending = await make_review(
        users[3], place, "Secret rooftop pool upstairs!", status="pending"
    )
    return {"place": place, "users": users, "reviews": reviews, "pending": pending}


def _label_of(prompt: str, body: str) -> str:
    line = next(line for line in prompt.splitlines() if body in line)
    return line.split("]")[0].lstrip("[")


def _wifi_reply(messages, tools) -> str:
    """A grounded one-point summary, whatever label the wifi review got."""
    label = _label_of(messages[-1]["content"], "Wifi is fast")
    return _reply(pros=[("Fast wifi", [label])])


async def _refresh() -> int:
    async with AsyncSessionLocal() as db:
        return await summary_service.refresh_stale(db, limit=10)


async def _summary(client, place):
    resp = await client.get(f"/api/v1/places/{place.id}/summary")
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_summary_is_built_from_published_reviews_with_citations(
    client, cafe, fake_ai
):
    def responder(messages, tools):
        prompt = messages[-1]["content"]
        assert "rooftop pool" not in prompt  # pending review never reaches the model
        wifi = _label_of(prompt, "Wifi is fast")
        price = _label_of(prompt, "350 taka")
        return _reply(
            pros=[("Fast wifi and you can stay for hours", [wifi])],
            cons=[
                ("Cold brew is pricey at 350 taka", [price]),
                ("Rooftop pool is closed", [wifi]),  # invented: dropped
            ],
        )

    fake_ai.llm.responder = responder
    assert (await _summary(client, cafe["place"]))["status"] == "pending"

    assert await _refresh() == 1
    body = await _summary(client, cafe["place"])
    assert body["status"] == "ready"
    assert body["stale"] is False
    assert body["based_on_reviews"] == 3
    assert body["model"] == "fake-llm"
    assert body["pros"] == [
        {
            "text": "Fast wifi and you can stay for hours",
            "review_ids": [str(cafe["reviews"][0].id)],
        }
    ]
    assert [c["text"] for c in body["cons"]] == ["Cold brew is pricey at 350 taka"]
    async with AsyncSessionLocal() as db:
        summary = await db.get(ReviewSummary, cafe["place"].id)
        assert summary.dropped_points == 1
        call = (await db.execute(select(LLMCall))).scalar_one()
        assert (call.purpose, call.status) == ("review_summary", "ok")
    assert fake_ai.llm.requests[0]["json_mode"] is True

    # Cached: reading it again costs nothing, and nothing is stale.
    await _summary(client, cafe["place"])
    assert await _refresh() == 0
    assert len(fake_ai.llm.requests) == 1


async def test_too_few_reviews_never_calls_the_model(client, make_place, fake_ai):
    place = await make_place()
    assert (await _summary(client, place))["status"] == "not_enough_reviews"
    assert await _refresh() == 0
    assert fake_ai.llm.requests == []


async def test_regenerates_after_enough_new_reviews(client, cafe, fake_ai, make_review):
    fake_ai.llm.responder = _wifi_reply
    await _refresh()
    for i, user in enumerate(cafe["users"][3:6]):
        if i == 0:  # users[3] already has the pending review; publish it instead
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(Review)
                    .where(Review.id == cafe["pending"].id)
                    .values(status="published")
                )
                await db.commit()
        else:
            await make_review(user, cafe["place"], f"New review number {i}.")
        expected_stale = i == 2
        assert (await _summary(client, cafe["place"]))["stale"] is expected_stale

    assert await _refresh() == 1
    body = await _summary(client, cafe["place"])
    assert body["based_on_reviews"] == 6
    assert body["stale"] is False


async def test_rejecting_a_used_review_regenerates_or_removes_summary(
    client, cafe, fake_ai, make_user
):
    fake_ai.llm.responder = _wifi_reply
    await _refresh()
    admin = await make_user(role="admin")
    used = cafe["reviews"][0]

    resp = await client.post(
        f"/api/v1/admin/reviews/{used.id}/reject",
        json={"reason": "spam"},
        headers=admin.headers,
    )
    assert resp.status_code == 204
    # Down to 2 published reviews: the summary is removed, not left citing
    # a rejected review.
    await _refresh()
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(ReviewSummary)) == 0
    assert (await _summary(client, cafe["place"]))["status"] == "not_enough_reviews"


async def test_edited_review_triggers_regeneration(client, cafe, fake_ai, make_user):
    await make_user()  # unrelated
    fake_ai.llm.responder = _wifi_reply
    await _refresh()
    # Re-approval after an edit bumps updated_at past generated_at.
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Review)
            .where(Review.id == cafe["reviews"][1].id)
            .values(body="Prices went down, cold brew is 250 taka now.")
        )
        await db.commit()
    assert (await _summary(client, cafe["place"]))["stale"] is True
    assert await _refresh() == 1
    assert "250 taka" in fake_ai.llm.requests[-1]["messages"][-1]["content"]


async def test_model_failure_keeps_previous_summary(client, cafe, fake_ai, make_review):
    fake_ai.llm.responder = _wifi_reply
    await _refresh()
    for user in cafe["users"][4:6]:
        await make_review(user, cafe["place"], "Another visit.")
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Review)
            .where(Review.id == cafe["pending"].id)
            .values(status="published")
        )
        await db.commit()

    fake_ai.llm.error = LLMError("provider down")
    assert await _refresh() == 0
    body = await _summary(client, cafe["place"])
    assert body["status"] == "ready"
    assert body["stale"] is True
    assert body["pros"][0]["text"] == "Fast wifi"


async def test_non_json_reply_is_not_saved(client, cafe, fake_ai):
    fake_ai.llm.responder = lambda m, t: "Sure! This cafe is lovely."
    assert await _refresh() == 0
    assert (await _summary(client, cafe["place"]))["status"] == "pending"


async def test_disabled_and_missing(client, cafe, monkeypatch, make_place):
    monkeypatch.setattr(settings, "AI_ENABLED", False)
    assert (await _summary(client, cafe["place"]))["status"] == "disabled"
    hidden = await make_place(verified=False)
    resp = await client.get(f"/api/v1/places/{hidden.id}/summary")
    assert resp.status_code == 404
