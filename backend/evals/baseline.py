"""A rule-based stand-in for the model, used by `--provider fake`.

Scripting the expected tool calls would score 100% and measure nothing, so the
offline agent eval runs this keyword planner instead: search with the user's
words, then plan the trip or read the details of the top result. It was
written alongside the cases and handles all of them, so its score says the
cases and harness are consistent, not that the task is easy: a real model
should match it on these phrasings and hold up on the ones rules can't parse.
It runs the real tools, search and database, so it also checks the harness end
to end without a model.
"""

import json
import re

from app.ai.fake import text_reply, tool_reply
from app.ai.types import ChatResult, Message, ToolSpec

AREAS = [
    "old dhaka", "puran dhaka", "nazira bazar", "dhanmondi", "gulshan", "banani",
    "uttara", "mirpur", "mohammadpur", "motijheel",
]  # fmt: skip

_TRIP = re.compile(r"\b(way|get to|go to|take me|bus|uber|pathao|ride|fare)\b", re.I)
_DETAILS = re.compile(r"\b(open|hours|people say|reviews?|closed)\b", re.I)
_ORIGIN = [
    re.compile(r"\bfrom ([a-z][\w ]*?)(?= to\b|[,.?!]|$)", re.I),
    re.compile(r"\bi'?m at ([a-z][\w ]*?)(?=[,.?!]|$)", re.I),
]
_HERE = re.compile(r"\b(from|starting from) here\b", re.I)


def _origin(text: str) -> str | None:
    if _HERE.search(text):
        return "current location"
    for pattern in _ORIGIN:
        if m := pattern.search(text):
            return m.group(1).strip()
    return None


def _near(text: str) -> str | None:
    lowered = text.lower()
    return next((a for a in AREAS if a in lowered), None)


def _query(text: str, origin: str | None) -> str:
    if origin and origin != "current location":
        text = re.sub(rf"\b(from|i'?m at) {re.escape(origin)}\b", "", text, flags=re.I)
    return " ".join(text.split())[:200]


def _results(messages: list[Message]) -> dict[str, dict]:
    """The last result of each tool so far, by tool name."""
    names = {
        tc["id"]: tc["function"]["name"]
        for m in messages
        if m["role"] == "assistant"
        for tc in m.get("tool_calls") or []
    }
    out = {}
    for m in messages:
        if m["role"] == "tool":
            try:
                out[names[m["tool_call_id"]]] = json.loads(m["content"])
            except (KeyError, ValueError):
                continue
    return out


def _answer(results: dict[str, dict]) -> str:
    found = results.get("search_places", {}).get("results") or []
    if not found:
        return "I couldn't find a matching place."
    lines = [f"Try **{found[0]['name']}** in {found[0]['area']}."]
    options = results.get("get_fare", {}).get("options") or []
    if options:
        lines.append(f"Cheapest: {options[0]['mode']} for ৳{options[0]['fare_bdt']}.")
    return " ".join(lines)


def respond(messages: list[Message], tools: list[ToolSpec] | None) -> ChatResult:
    text = next(m["content"] for m in reversed(messages) if m["role"] == "user")
    if tools is None:  # the final nudge: tools are off
        return text_reply(_answer(_results(messages)))
    origin = _origin(text)
    results = _results(messages)
    step = sum(1 for m in messages if m["role"] == "tool")  # for unique call ids

    if "search_places" not in results:
        if _TRIP.search(text) and not origin:
            return text_reply("Where are you starting from?")
        args = {"query": _query(text, origin)}
        if near := _near(text):
            args["near"] = near
        return tool_reply(("search_places", args), id_prefix=f"s{step}")

    found = results["search_places"].get("results") or []
    if not found:
        return text_reply(_answer(results))
    place = found[0]["place_id"]
    if origin and _TRIP.search(text) and len(results) == 1:
        if re.search(r"\bbus\b", text, re.I):
            tool = "get_bus_route"
        elif re.search(r"\b(uber|pathao|ride)\b", text, re.I):
            tool = "get_ridehail_estimate"
        else:
            tool = "get_fare"
        return tool_reply(
            (tool, {"origin": origin, "place": place}), id_prefix=f"s{step}"
        )
    if _DETAILS.search(text) and "get_place_details" not in results:
        return tool_reply(("get_place_details", {"place": place}), id_prefix=f"s{step}")
    return text_reply(_answer(results))
