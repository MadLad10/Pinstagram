"""Trip-planning assistant: the tool-calling loop, SSE stream, limits and
failure handling. The LLM is scripted (FakeLLM); tools, search, directions and
the database are real."""

import asyncio
import json

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import select

from app.ai import tools as tools_module
from app.ai.fake import text_reply, tool_reply
from app.ai.indexing import embed_all
from app.ai.tools import TOOLS, ToolContext, ToolError, resolve_location
from app.ai.types import ChatResult, LLMRateLimited, ToolCall
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.llm_call import LLMCall
from app.models.transport import BusRoute, BusStop, TransportFare

QUESTION = "cheapest way from Mirpur 10 to a good biryani place near Old Dhaka"


def _pt(lat, lng):
    return WKTElement(f"POINT({lng} {lat})", srid=4326)


@pytest.fixture
async def city(make_place, make_user, make_review):
    """Mirpur 10 → Gulistan on one bus line; a biryani house near Gulistan."""
    async with AsyncSessionLocal() as db:
        stops = [
            BusStop(name=name, location=_pt(lat, lng))
            for name, lat, lng in [
                ("Mirpur 10", 23.8069, 90.3687),
                ("Farmgate", 23.7577, 90.3897),
                ("Gulistan", 23.7234, 90.4113),
            ]
        ]
        db.add_all(stops)
        await db.flush()
        db.add(
            BusRoute(
                name="Mirpur–Motijheel",
                operator="BRTC",
                stops=[str(s.id) for s in stops],
                typical_fare=40,
                typical_duration_min=70,
            )
        )
        db.add(TransportFare(provider="pathao", base_fare=40, per_km=16, per_min=2))
        await db.commit()

    biryani = await make_place(
        "Old Dhaka Biryani House",
        category="restaurant",
        area="Nazira Bazar",
        lat=23.7203,
        lng=90.4030,
        price_tier="budget",
        description="Haji-style beef biryani and borhani.",
    )
    kacchi = await make_place(
        "Kacchi Ghor",
        category="restaurant",
        area="Dhanmondi",
        lat=23.7461,
        lng=90.3742,
        description="Mutton kacchi biryani.",
    )
    author = await make_user("Critic")
    await make_review(author, biryani, "Biryani sells out by 3 pm, come early.")
    async with AsyncSessionLocal() as db:
        await embed_all(db)
    return {"biryani": biryani, "kacchi": kacchi}


@pytest.fixture
async def user(make_user):
    return await make_user("Traveller")


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        name_line, data_line = block.split("\n")
        events.append((name_line.removeprefix("event: "), json.loads(data_line[6:])))
    return events


async def _chat(client, user, text=QUESTION, **extra):
    resp = await client.post(
        "/api/v1/assistant/chat",
        json={"messages": [{"role": "user", "content": text}], **extra},
        headers=user.headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    return parse_sse(resp.text)


def _of(events, kind):
    return [data for name, data in events if name == kind]


def _answer(events) -> str:
    return "".join(d["text"] for d in _of(events, "token"))


async def test_plans_a_trip_with_existing_services(client, city, user, fake_ai):
    fake_ai.llm.queue(
        tool_reply(("search_places", {"query": "biryani", "near": "Old Dhaka"})),
        tool_reply(
            ("get_fare", {"origin": "Mirpur 10", "place": "Old Dhaka Biryani House"})
        ),
        text_reply(
            "Cheapest: take the Mirpur–Motijheel bus from Mirpur 10 to Gulistan "
            "for ৳40, then walk to Old Dhaka Biryani House. Come before 3 pm."
        ),
    )
    events = await _chat(client, user)

    assert [name for name, _ in events if name != "token"] == [
        "tool_call",
        "tool_result",
        "tool_call",
        "tool_result",
        "sources",
        "done",
    ]
    search, fare = _of(events, "tool_result")
    assert search["ok"] and search["summary"].startswith("Found")
    assert "Old Dhaka Biryani House" in search["summary"]
    assert fare["ok"] and fare["summary"].endswith("cheapest bus ৳40")

    # The model saw real tool output: the bus route and its fare.
    fare_message = fake_ai.llm.requests[2]["messages"][-1]
    assert fare_message["role"] == "tool"
    fare_payload = json.loads(fare_message["content"])
    bus = next(o for o in fare_payload["options"] if o["mode"] == "bus")
    assert (bus["bus"], bus["board_at"], bus["get_off_at"], bus["fare_bdt"]) == (
        "Mirpur–Motijheel",
        "Mirpur 10",
        "Gulistan",
        40,
    )
    assert fare_payload["origin"] == "Mirpur 10 (bus stop)"
    # Search ranked by distance from Old Dhaka: the nearby house comes first.
    search_payload = json.loads(fake_ai.llm.requests[1]["messages"][-1]["content"])
    assert search_payload["results"][0]["name"] == "Old Dhaka Biryani House"

    assert "৳40" in _answer(events)
    [sources] = _of(events, "sources")
    assert [p["name"] for p in sources["places"]] == ["Old Dhaka Biryani House"]
    assert {r["mode"] for r in sources["routes"]} >= {"bus", "ride_hail"}
    [done] = _of(events, "done")
    assert done["finish_reason"] == "answer"
    assert (done["steps"], done["tool_calls"]) == (3, 2)
    assert done["grounding"] == {
        "cited_places": [str(city["biryani"].id)],
        "unverified_places": [],
        "unsupported_fares": [],
    }

    first = fake_ai.llm.requests[0]
    assert first["messages"][0]["role"] == "system"
    assert {t.name for t in first["tools"]} == set(TOOLS)
    async with AsyncSessionLocal() as db:
        calls = (await db.execute(select(LLMCall))).scalars().all()
    assistant_calls = [c for c in calls if c.purpose == "assistant"]
    assert len(assistant_calls) == 3
    assert {c.user_id for c in assistant_calls} == {user.id}


async def test_tool_errors_go_back_to_the_model(client, city, user, fake_ai):
    fake_ai.llm.queue(
        tool_reply(
            ("get_bus_route", {"origin": "Mirpur 10", "place": "Atlantis Palace"})
        ),
        text_reply("I couldn't find that place. Could you check the name?"),
    )
    events = await _chat(client, user)
    [result] = _of(events, "tool_result")
    assert result["ok"] is False
    assert "No place matches 'Atlantis Palace'" in result["summary"]
    tool_message = fake_ai.llm.requests[1]["messages"][-1]
    assert "error" in json.loads(tool_message["content"])
    assert _of(events, "done")[0]["finish_reason"] == "answer"


async def test_unknown_tools_and_bad_arguments_are_reported(
    client, city, user, fake_ai
):
    bad_json = ChatResult(
        content="",
        tool_calls=[
            ToolCall(id="a", name="teleport", arguments={}),
            ToolCall(id="b", name="search_places", arguments={"query": "x"}),
            ToolCall(
                id="c",
                name="get_fare",
                arguments={},
                raw_arguments='{"origin": ',
                arguments_valid=False,
            ),
        ],
        model="fake-llm",
    )
    fake_ai.llm.queue(bad_json, text_reply("Sorry, something went wrong on my side."))
    events = await _chat(client, user)
    results = _of(events, "tool_result")
    assert [r["ok"] for r in results] == [False, False, False]
    assert "Unknown tool 'teleport'" in results[0]["summary"]
    assert "query" in results[1]["summary"]
    assert "not valid JSON" in results[2]["summary"]
    # Each call got exactly one reply, so the next request is well-formed.
    tool_ids = [
        m["tool_call_id"]
        for m in fake_ai.llm.requests[1]["messages"]
        if m["role"] == "tool"
    ]
    assert tool_ids == ["a", "b", "c"]


async def test_extra_calls_in_one_step_are_skipped(client, city, user, fake_ai):
    calls = [("search_places", {"query": f"biryani {i}"}) for i in range(6)]
    fake_ai.llm.queue(tool_reply(*calls), text_reply("Done."))
    events = await _chat(client, user)
    assert len(_of(events, "tool_call")) == 4
    tool_messages = [
        m for m in fake_ai.llm.requests[1]["messages"] if m["role"] == "tool"
    ]
    assert len(tool_messages) == 6
    assert "Skipped" in tool_messages[-1]["content"]


async def test_step_limit_forces_an_answer(client, city, user, fake_ai, monkeypatch):
    monkeypatch.setattr(settings, "ASSISTANT_MAX_STEPS", 2)

    def responder(messages, tools):
        if tools is None:
            return "Here is what I found so far: Old Dhaka Biryani House."
        return tool_reply(("search_places", {"query": "biryani"}))

    fake_ai.llm.responder = responder
    events = await _chat(client, user)
    [done] = _of(events, "done")
    assert done["finish_reason"] == "max_steps"
    assert (done["steps"], done["tool_calls"]) == (3, 2)
    last = fake_ai.llm.requests[-1]
    assert last["tools"] is None
    assert "used all your tool calls" in last["messages"][-1]["content"]


async def test_slow_tool_times_out_without_ending_the_chat(
    client, city, user, fake_ai, monkeypatch
):
    async def slow(db, args, ctx):
        await asyncio.sleep(5)

    monkeypatch.setattr(TOOLS["search_places"], "handler", slow)
    monkeypatch.setattr(settings, "ASSISTANT_TOOL_TIMEOUT_S", 0.05)
    fake_ai.llm.queue(
        tool_reply(("search_places", {"query": "biryani"})),
        text_reply("Search is slow right now, please try again."),
    )
    events = await _chat(client, user)
    [result] = _of(events, "tool_result")
    assert result == {
        "id": "call_0",
        "name": "search_places",
        "ok": False,
        "summary": "search_places timed out. Try again or use another tool.",
    }
    assert _of(events, "done")[0]["finish_reason"] == "answer"


async def test_request_deadline_ends_the_stream(
    client, city, user, fake_ai, monkeypatch
):
    async def slow(db, args, ctx):
        await asyncio.sleep(5)

    monkeypatch.setattr(TOOLS["search_places"], "handler", slow)
    monkeypatch.setattr(settings, "ASSISTANT_TIMEOUT_S", 0.2)
    fake_ai.llm.queue(tool_reply(("search_places", {"query": "biryani"})))
    events = await _chat(client, user)
    [error] = _of(events, "error")
    assert error["code"] == "timeout"
    assert _of(events, "done")[0]["finish_reason"] == "timeout"


async def test_rate_limited_model(client, city, user, fake_ai):
    fake_ai.llm.error = LLMRateLimited(retry_after=30)
    events = await _chat(client, user)
    assert _of(events, "error")[0]["code"] == "rate_limited"
    assert _of(events, "done")[0]["finish_reason"] == "error"
    async with AsyncSessionLocal() as db:
        statuses = (await db.execute(select(LLMCall.status))).scalars().all()
    assert "error" in statuses


async def test_grounding_flags_places_and_fares_the_tools_never_returned(
    client, city, user, fake_ai
):
    fake_ai.llm.queue(
        text_reply("Try Kacchi Ghor, a rickshaw there is about 999 taka.")
    )
    events = await _chat(client, user)
    [done] = _of(events, "done")
    assert done["grounding"] == {
        "cited_places": [],
        "unverified_places": ["Kacchi Ghor"],
        "unsupported_fares": ["999"],
    }
    assert _of(events, "sources")[0] == {"places": [], "routes": []}


async def test_text_before_a_tool_call_is_part_of_the_answer(
    client, city, user, fake_ai
):
    fake_ai.llm.queue(
        tool_reply(
            ("search_places", {"query": "biryani", "near": "Old Dhaka"}),
            content="A rickshaw is 500 taka.",
        ),
        text_reply("Old Dhaka Biryani House is closest."),
    )
    events = await _chat(client, user)
    assert _answer(events) == (
        "A rickshaw is 500 taka.\n\nOld Dhaka Biryani House is closest."
    )
    # Fares shown in any step are checked, not just the last one.
    assert _of(events, "done")[0]["grounding"]["unsupported_fares"] == ["500"]
    search = json.loads(fake_ai.llm.requests[1]["messages"][-1]["content"])
    assert "km_from_near" in search["results"][0]


async def test_current_location_is_used_as_origin(client, city, user, fake_ai):
    fake_ai.llm.queue(
        tool_reply(
            (
                "get_ridehail_estimate",
                {"origin": "current location", "place": "Kacchi Ghor"},
            )
        ),
        text_reply("A Pathao costs about that."),
    )
    events = await _chat(client, user, location={"lat": 23.8069, "lng": 90.3687})
    assert _of(events, "tool_result")[0]["ok"]
    assert "23.80690,90.36870" in fake_ai.llm.requests[0]["messages"][0]["content"]
    payload = json.loads(fake_ai.llm.requests[1]["messages"][-1]["content"])
    assert payload["origin"] == "your current location"
    assert payload["estimate"]["providers"][0]["name"] == "pathao"


async def test_request_validation_auth_and_switches(
    client, user, make_user, monkeypatch
):
    url = "/api/v1/assistant/chat"
    one = {"messages": [{"role": "user", "content": "hi"}]}
    assert (await client.post(url, json=one)).status_code == 401
    ends_with_assistant = {"messages": [{"role": "assistant", "content": "hi"}]}
    resp = await client.post(url, json=ends_with_assistant, headers=user.headers)
    assert resp.status_code == 422

    monkeypatch.setattr(settings, "AI_ENABLED", False)
    assert (await client.post(url, json=one, headers=user.headers)).status_code == 503


async def test_daily_token_budget(client, user, monkeypatch):
    monkeypatch.setattr(settings, "ASSISTANT_DAILY_TOKENS", 1000)
    async with AsyncSessionLocal() as db:
        db.add(
            LLMCall(
                purpose="assistant",
                provider="fake",
                model="fake-llm",
                user_id=user.id,
                input_tokens=900,
                output_tokens=150,
                latency_ms=10,
                status="ok",
            )
        )
        await db.commit()
    resp = await client.post(
        "/api/v1/assistant/chat",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers=user.headers,
    )
    assert resp.status_code == 429


# -------------------------------------------------------------------- tools


async def test_resolve_location(city):
    ctx = ToolContext()
    async with AsyncSessionLocal() as db:
        stop = await resolve_location(db, "mirpur10", ctx)
        assert (stop.name, stop.kind) == ("Mirpur 10", "bus_stop")
        assert (await resolve_location(db, "Puran Dhaka", ctx)).name == "Old Dhaka"
        assert (await resolve_location(db, "23.75, 90.39", ctx)).lat == 23.75
        place = await resolve_location(db, "old dhaka biryani house", ctx)
        assert place.kind == "place"
        with pytest.raises(ToolError, match="current location isn't available"):
            await resolve_location(db, "my location", ctx)
        with pytest.raises(ToolError, match="Couldn't find"):
            await resolve_location(db, "Qwertyville", ctx)


async def test_bus_route_reports_when_no_bus_serves_the_trip(city):
    ctx = ToolContext()
    async with AsyncSessionLocal() as db:
        result = await tools_module.get_bus_route(
            db,
            tools_module.TripArgs(origin="Mirpur 10", place="Kacchi Ghor"),
            ctx,
        )
    assert result["available"] is False
    assert ctx.routes == []


def test_tool_schemas_are_plain_json_schema():
    for tool in TOOLS.values():
        schema = tool.spec.parameters
        dumped = json.dumps(schema)
        assert "anyOf" not in dumped and '"title"' not in dumped
        assert schema["type"] == "object"
    search = TOOLS["search_places"].spec.parameters
    assert search["required"] == ["query"]
    assert search["properties"]["category"]["enum"][0] == "hotel"


async def test_closing_the_stream_cancels_the_work(city, fake_ai, monkeypatch):
    """A client disconnect closes the event iterator; the running tool must
    be cancelled rather than left running in the background."""
    from app.ai.agent import run_agent

    started, cancelled = asyncio.Event(), asyncio.Event()

    async def slow(db, args, ctx):
        started.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    monkeypatch.setattr(TOOLS["search_places"], "handler", slow)
    fake_ai.llm.queue(tool_reply(("search_places", {"query": "biryani"})))
    events = run_agent([{"role": "user", "content": "biryani?"}])
    assert (await anext(events)).type == "tool_call"
    await asyncio.wait_for(started.wait(), 1)
    await asyncio.wait_for(events.aclose(), 1)
    assert cancelled.is_set()
