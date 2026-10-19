"""Trip-planning assistant: an LLM tool-calling loop over the tools in
app.ai.tools, streamed as events.

Limits and failure handling:
- at most ASSISTANT_MAX_STEPS model calls with tools; after that the model is
  asked to answer from what it has, with tools disabled
- each tool call has its own timeout and database session; a tool that fails,
  times out, or gets invalid arguments returns an error result the model can
  read and recover from, instead of failing the request
- the whole request has a deadline; rate limits and provider errors end the
  stream with an `error` event

The loop runs in its own task and hands events to the HTTP response through a
queue, so the deadline and client disconnects cancel the work cleanly.

Event types: token, tool_call, tool_result, sources, error, done.
"""

import asyncio
import json
import logging
import re
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime

from pydantic import ValidationError
from sqlalchemy import select

from app.ai import get_llm
from app.ai.tools import TOOLS, ToolContext, ToolError
from app.ai.types import (
    ChatResult,
    LLMError,
    LLMRateLimited,
    LLMTimeout,
    Message,
    TextDelta,
    ToolCall,
)
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.place import Place
from app.services.directions_service import DHAKA_TZ

log = logging.getLogger(__name__)

MAX_CALLS_PER_STEP = 4
MAX_TOOL_RESULT_CHARS = 6000

SYSTEM_PROMPT = """You are Pinstagram's trip planner for Dhaka, Bangladesh. You help people choose places and get there cheaply and quickly.

Always use the tools; never answer from memory:
- search_places finds places. Pass `near` when the user names an area. Its results have no opening hours or reviews.
- get_place_details gives opening hours, amenities and what reviewers say. Call it whenever the user asks if a place is open, about its hours, or what people say about it.
- get_fare compares every way to get somewhere (bus, ride-hail, train, walking). Use get_bus_route or get_ridehail_estimate for one mode in detail.

Rules:
- Cover every part of the question with a tool before answering. "Find a place and tell me how to get there" needs search_places, then a route or fare tool for the place you picked.
- Only recommend places that tools returned in this conversation, and only quote fares, times and routes that tools returned. If a tool found nothing or failed, say so plainly instead of guessing.
- Fares are in Bangladeshi taka (৳). When you suggest a bus, name the bus and where to get on and off.
- If you don't know where the trip starts, ask.
- Keep answers short: the recommendation, the route and its cost, and one useful tip from reviews if there is one.

Now: {now} (Dhaka time).{location}"""

FINAL_NUDGE = (
    "You have used all your tool calls. Answer now using only the tool results "
    "above, and say briefly what you couldn't check."
)


@dataclass
class AgentEvent:
    type: str
    data: dict


def _system_prompt(user_location: tuple[float, float] | None) -> str:
    location = (
        f"\nThe user's current location is {user_location[0]:.5f},{user_location[1]:.5f}; "
        "use origin 'current location' for trips from where they are."
        if user_location
        else ""
    )
    now = datetime.now(DHAKA_TZ).strftime("%A %d %B %Y, %H:%M")
    return SYSTEM_PROMPT.format(now=now, location=location)


async def _execute(call: ToolCall, ctx: ToolContext) -> tuple[bool, dict]:
    tool = TOOLS.get(call.name)
    if tool is None:
        return False, {
            "error": f"Unknown tool '{call.name}'. Available: {', '.join(TOOLS)}."
        }
    if not call.arguments_valid:
        return False, {
            "error": f"Arguments were not valid JSON: {call.raw_arguments[:200]}"
        }
    try:
        args = tool.args_model.model_validate(call.arguments)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(map(str, e['loc'])) or 'arguments'}: {e['msg']}"
            for e in exc.errors()
        )
        return False, {"error": f"Invalid arguments: {problems}"}
    try:
        async with asyncio.timeout(settings.ASSISTANT_TOOL_TIMEOUT_S):
            # A session per call: a failed or cancelled query can't poison the next.
            async with AsyncSessionLocal() as db:
                return True, await tool.handler(db, args, ctx)
    except ToolError as exc:
        return False, {"error": str(exc)}
    except TimeoutError:
        return False, {
            "error": f"{call.name} timed out. Try again or use another tool."
        }
    except Exception as exc:  # a bug or outage in one tool shouldn't end the chat
        log.exception("Tool %s failed", call.name)
        return False, {
            "error": f"{call.name} failed unexpectedly ({type(exc).__name__})."
        }


def _tool_message(call: ToolCall, payload: dict) -> Message:
    content = json.dumps(
        payload, ensure_ascii=False, default=str, separators=(",", ":")
    )
    if len(content) > MAX_TOOL_RESULT_CHARS:
        content = content[:MAX_TOOL_RESULT_CHARS] + "…(truncated)"
    return {"role": "tool", "tool_call_id": call.id, "content": content}


def _result_summary(name: str, ok: bool, payload: dict) -> str:
    """One line for the UI's tool step chips."""
    if not ok:
        return payload["error"]
    if name == "search_places":
        names = [r["name"] for r in payload["results"][:3]]
        return (
            f"Found {len(payload['results'])}: {', '.join(names)}"
            if names
            else "No matches"
        )
    if name == "get_fare":
        cheapest = payload["options"][0] if payload["options"] else None
        return (
            f"{len(payload['options'])} options, cheapest {cheapest['mode']} ৳{cheapest['fare_bdt']}"
            if cheapest
            else "No options"
        )
    if name == "get_bus_route":
        if not payload["available"]:
            return "No direct bus"
        r = payload["route"]
        return f"{r['bus']}: {r['board_at']} → {r['get_off_at']}, ৳{r['fare_bdt']}"
    if name == "get_ridehail_estimate":
        e = payload["estimate"]
        return f"Ride-hail from ৳{e['fare_bdt']}, ~{e['duration_min']} min"
    return payload.get("name", "Done")


_FARE = re.compile(
    r"(?:৳|\btk\.?|\btaka\b|\bbdt\b)\s*(\d[\d,]*)|(\d[\d,]*)\s*(?:৳|\btk\b|\btaka\b|\bbdt\b)",
    re.IGNORECASE,
)


async def check_grounding(
    answer: str, ctx: ToolContext, tool_payloads: list[str]
) -> dict:
    """Which known places the answer names, whether the tools returned them,
    and whether the fares it quotes appear in tool results."""
    async with AsyncSessionLocal() as db:
        known = (
            await db.execute(
                select(Place.id, Place.name).where(Place.is_verified.is_(True))
            )
        ).all()
    lowered = answer.lower()
    mentioned = [(pid, name) for pid, name in known if name.lower() in lowered]
    tool_numbers = set(re.findall(r"\d+", " ".join(tool_payloads)))
    fares = {(a or b).replace(",", "") for a, b in _FARE.findall(answer) if (a or b)}
    return {
        "cited_places": [str(pid) for pid, _ in mentioned if pid in ctx.places],
        "unverified_places": [name for pid, name in mentioned if pid not in ctx.places],
        "unsupported_fares": sorted(f for f in fares if f not in tool_numbers),
    }


async def _run(
    history: list[Message],
    user_id: uuid.UUID | None,
    user_location: tuple[float, float] | None,
    emit: Callable[[AgentEvent], None],
) -> None:
    llm = get_llm()
    ctx = ToolContext(user_location=user_location)
    messages: list[Message] = [
        {"role": "system", "content": _system_prompt(user_location)},
        *history,
    ]
    tool_payloads: list[str] = []
    answer: list[str] = []
    steps = tool_calls = 0
    finish = "answer"
    max_steps = settings.ASSISTANT_MAX_STEPS

    try:
        async with asyncio.timeout(settings.ASSISTANT_TIMEOUT_S):
            for step in range(max_steps + 1):
                final_step = step == max_steps
                if final_step:
                    messages.append({"role": "user", "content": FINAL_NUDGE})
                result: ChatResult | None = None
                step_started = False
                async for event in llm.stream(
                    messages,
                    purpose="assistant",
                    tools=None if final_step else [t.spec for t in TOOLS.values()],
                    user_id=user_id,
                ):
                    if isinstance(event, TextDelta):
                        # Text written before a tool call is shown too, so it is
                        # part of the answer: separate it from the next step's.
                        if not step_started and answer:
                            answer.append("\n\n")
                            emit(AgentEvent("token", {"text": "\n\n"}))
                        step_started = True
                        answer.append(event.text)
                        emit(AgentEvent("token", {"text": event.text}))
                    else:
                        result = event
                steps += 1
                if final_step or not result.tool_calls:
                    finish = "max_steps" if final_step else "answer"
                    break

                messages.append(result.as_message())
                for i, call in enumerate(result.tool_calls):
                    if i >= MAX_CALLS_PER_STEP:
                        # Every call needs a reply for the next request to be valid.
                        messages.append(
                            _tool_message(
                                call, {"error": "Skipped: too many calls at once."}
                            )
                        )
                        continue
                    tool_calls += 1
                    emit(
                        AgentEvent(
                            "tool_call",
                            {
                                "id": call.id,
                                "name": call.name,
                                "arguments": call.arguments,
                            },
                        )
                    )
                    ok, payload = await _execute(call, ctx)
                    message = _tool_message(call, payload)
                    tool_payloads.append(message["content"])
                    messages.append(message)
                    emit(
                        AgentEvent(
                            "tool_result",
                            {
                                "id": call.id,
                                "name": call.name,
                                "ok": ok,
                                "summary": _result_summary(call.name, ok, payload),
                            },
                        )
                    )
    except (TimeoutError, LLMTimeout):
        finish = "timeout"
        emit(
            AgentEvent(
                "error",
                {
                    "code": "timeout",
                    "message": "The assistant took too long. Try a simpler question.",
                },
            )
        )
    except LLMRateLimited:
        finish = "error"
        emit(
            AgentEvent(
                "error",
                {
                    "code": "rate_limited",
                    "message": "The assistant is busy right now. Try again in a minute.",
                },
            )
        )
    except LLMError as exc:
        finish = "error"
        log.warning("Assistant model call failed: %s", exc)
        emit(
            AgentEvent(
                "error",
                {
                    "code": "llm_error",
                    "message": "The assistant is unavailable right now.",
                },
            )
        )

    text = "".join(answer)
    grounding = (
        await check_grounding(text, ctx, tool_payloads)
        if text
        else {
            "cited_places": [],
            "unverified_places": [],
            "unsupported_fares": [],
        }
    )
    if grounding["unverified_places"] or grounding["unsupported_fares"]:
        log.warning("Assistant answer not fully grounded: %s", grounding)
    # Cards for the places the answer talks about (or everything found, if
    # it named none), with the routes planned to them.
    cited = [uuid.UUID(pid) for pid in grounding["cited_places"]] or list(ctx.places)
    places = [ctx.places[pid] for pid in cited][:5]
    shown = {p["id"] for p in places}
    emit(
        AgentEvent(
            "sources",
            {
                "places": places,
                "routes": [r for r in ctx.routes if r["place_id"] in shown],
            },
        )
    )
    emit(
        AgentEvent(
            "done",
            {
                "finish_reason": finish,
                "steps": steps,
                "tool_calls": tool_calls,
                "grounding": grounding,
            },
        )
    )


async def run_agent(
    history: list[Message],
    *,
    user_id: uuid.UUID | None = None,
    user_location: tuple[float, float] | None = None,
) -> AsyncIterator[AgentEvent]:
    """Stream the assistant's events. Closing the iterator (e.g. the client
    disconnected) cancels the work."""
    queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()

    async def produce() -> None:
        try:
            await _run(history, user_id, user_location, queue.put_nowait)
        except Exception:
            log.exception("Assistant crashed")
            queue.put_nowait(
                AgentEvent(
                    "error", {"code": "internal", "message": "Something went wrong."}
                )
            )
            queue.put_nowait(AgentEvent("done", {"finish_reason": "error"}))
        finally:
            queue.put_nowait(None)

    task = asyncio.create_task(produce(), name="assistant")
    try:
        while (event := await queue.get()) is not None:
            yield event
    finally:
        if not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
