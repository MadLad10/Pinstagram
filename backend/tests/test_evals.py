"""The eval harness (backend/evals): scoring functions, the rule-based
planner, and that every case still names places the dev seed has."""

import json
from pathlib import Path

from app.scripts.seed_dev import PLACES
from evals import baseline
from evals.metrics import (
    arg_matches,
    first_relevant_rank,
    hit_at,
    percentile,
    precision_recall,
    reciprocal_rank,
    score_tool_use,
)
from evals.run import eval_database_url, markdown

EVALS = Path(__file__).parent.parent / "evals"
PLACE_ID = "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed"


def test_ranking_metrics():
    ranked = ["A", "B", "C", "D"]
    assert first_relevant_rank(ranked, {"C", "D"}) == 3
    assert first_relevant_rank(ranked, {"Z"}) is None
    assert hit_at(3, 3) == 1.0 and hit_at(4, 3) == 0.0 and hit_at(None, 5) == 0.0
    assert reciprocal_rank(4) == 0.25 and reciprocal_rank(None) == 0.0
    assert percentile([5, 1, 3, 2, 4], 50) == 3
    assert percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95) == 10
    assert percentile([], 50) is None


def test_arg_matches_by_substring_and_place_id():
    names = {PLACE_ID: "Old Dhaka Biryani House"}
    assert arg_matches("Mirpur 10 bus stop", ["mirpur 10"], names)
    assert arg_matches(PLACE_ID, ["biryani"], names)
    assert not arg_matches("Mirpur 1", ["mirpur 10"], names)
    assert not arg_matches(None, ["x"], names)


def test_score_tool_use():
    names = {PLACE_ID: "Old Dhaka Biryani House"}
    expected = [
        {"name": "search_places", "args": {"query": ["biryani"]}},
        {"name": "get_fare", "args": {"origin": ["mirpur 10"], "place": ["biryani"]}},
    ]
    calls = [
        {"name": "search_places", "args": {"query": "biryani"}},
        {"name": "get_place_details", "args": {"place": PLACE_ID}},
        {"name": "get_ridehail_estimate", "args": {"origin": "x", "place": "y"}},
        {"name": "get_fare", "args": {"origin": "Farmgate", "place": PLACE_ID}},
    ]
    score = score_tool_use(calls, expected, {"get_place_details"}, names)
    assert (score["tp"], score["fp"], score["fn"]) == (2, 1, 0)
    assert score["unexpected"] == ["get_ridehail_estimate"]
    assert (score["args_ok"], score["args_total"]) == (2, 3)
    assert score["wrong_args"][0].startswith("get_fare.origin")

    # Asking for the origin instead of guessing one calls nothing.
    nothing = score_tool_use([], [], {"search_places"}, names)
    assert (nothing["tp"], nothing["fp"], nothing["fn"]) == (0, 0, 0)
    assert precision_recall([score, nothing]) == (2 / 3, 1.0)
    assert precision_recall([nothing]) == (None, None)


def test_baseline_plans_trips():
    user = {
        "role": "user",
        "content": "Which bus do I take from Farmgate to Lalbagh Fort?",
    }
    first = baseline.respond([user], tools=[])
    [search] = first.tool_calls
    assert search.name == "search_places"
    assert "farmgate" not in search.arguments["query"].lower()

    found = {
        "results": [{"place_id": PLACE_ID, "name": "Lalbagh Fort", "area": "Lalbagh"}]
    }
    history = [
        user,
        first.as_message(),
        {"role": "tool", "tool_call_id": search.id, "content": json.dumps(found)},
    ]
    [trip] = baseline.respond(history, tools=[]).tool_calls
    assert trip.name == "get_bus_route"
    assert trip.arguments == {"origin": "Farmgate", "place": PLACE_ID}
    assert trip.id != search.id


def test_baseline_asks_for_a_missing_origin():
    user = {"role": "user", "content": "How do I get to Star Mosque cheaply?"}
    reply = baseline.respond([user], tools=[])
    assert not reply.tool_calls and "starting from" in reply.content


def test_cases_name_seeded_places():
    seeded = {p[0] for p in PLACES}
    for case in json.loads((EVALS / "search_cases.json").read_text()):
        assert set(case["expected"]) <= seeded, case["id"]
    ids = [c["id"] for c in json.loads((EVALS / "agent_cases.json").read_text())]
    assert len(ids) == len(set(ids))


def test_report_markdown():
    assert (
        eval_database_url("postgresql+asyncpg://u:p@h:5432/bdvisual")
        == "postgresql+asyncpg://u:p@h:5432/bdvisual_eval"
    )
    case = {
        "id": "q",
        "query": "kacchi",
        "expected": ["Kacchi Ghor"],
        "top": ["Kacchi Ghor"],
    }
    search_metrics = {
        "hit@3": 1.0,
        "hit@5": 1.0,
        "mrr": 1.0,
        "p50_ms": 5,
        "p95_ms": 1500,
    }
    report = {
        "meta": {
            "provider": "fake",
            "llm_model": "fake-llm",
            "embedding_model": "fake-embed",
            "database": "bdvisual_eval",
            "started_at": "now",
        },
        "search": {
            "keyword": {
                "metrics": search_metrics | {"fallbacks": 0},
                "cases": [case | {"rank": None}],
            },
            "hybrid": {
                "metrics": search_metrics | {"fallbacks": 1},
                "cases": [case | {"rank": 1}],
            },
        },
    }
    text = markdown(report)
    assert "| hybrid | 1.00 | 1.00 | 1.00 | 5 ms | 1.5 s |" in text
    assert "| kacchi | Kacchi Ghor | — | 1 | Kacchi Ghor |" in text
    assert "fell back to keyword search on 1 of 1" in text
