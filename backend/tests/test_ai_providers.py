"""Provider layer: OpenAI-compatible wire format, streaming, errors, cost
logging. HTTP is mocked with httpx.MockTransport; nothing leaves the process."""

import json
import math

import httpx
import pytest
from sqlalchemy import select

from app.ai import pricing
from app.ai.openai_compat import OpenAICompatEmbedder, OpenAICompatLLM
from app.ai.types import (
    ChatResult,
    LLMError,
    LLMRateLimited,
    LLMTimeout,
    TextDelta,
    ToolSpec,
)
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.llm_call import LLMCall

TOOL = ToolSpec(
    name="search_places",
    description="Find places",
    parameters={"type": "object", "properties": {"query": {"type": "string"}}},
)


def _llm(handler, model="gemini-2.5-flash") -> OpenAICompatLLM:
    return OpenAICompatLLM(
        base_url="http://llm.test/v1",
        api_key="k",
        model=model,
        transport=httpx.MockTransport(handler),
    )


async def _calls() -> list[LLMCall]:
    async with AsyncSessionLocal() as db:
        return list((await db.execute(select(LLMCall))).scalars())


async def test_chat_parses_tool_calls_and_logs_usage_and_cost():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "gemini-2.5-flash",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "c1",
                                    "type": "function",
                                    "function": {
                                        "name": "search_places",
                                        "arguments": '{"query": "biryani"}',
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 200},
            },
        )

    result = await _llm(handler).chat(
        [{"role": "user", "content": "hi"}], purpose="test", tools=[TOOL]
    )

    assert seen["url"] == "http://llm.test/v1/chat/completions"
    assert seen["auth"] == "Bearer k"
    assert seen["body"]["tools"][0]["function"]["name"] == "search_places"
    assert result.tool_calls[0].name == "search_places"
    assert result.tool_calls[0].arguments == {"query": "biryani"}
    # The assistant turn round-trips into the next request unchanged.
    assert result.as_message()["tool_calls"][0]["function"]["arguments"] == (
        '{"query": "biryani"}'
    )

    [row] = await _calls()
    assert (row.purpose, row.model, row.status) == ("test", "gemini-2.5-flash", "ok")
    assert (row.input_tokens, row.output_tokens) == (1000, 200)
    assert not row.tokens_estimated
    assert row.latency_ms >= 0
    # Free tier: billed $0, list price 1000*0.30/1M + 200*2.50/1M.
    assert float(row.cost_usd) == 0
    assert float(row.list_cost_usd) == pytest.approx(0.0008)


async def test_stream_assembles_fragmented_tool_calls():
    chunks = [
        {"choices": [{"delta": {"content": "Let me "}}]},
        {"choices": [{"delta": {"content": "check."}}]},
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "c1",
                                "function": {"name": "search_", "arguments": '{"qu'},
                            }
                        ]
                    }
                }
            ]
        },
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {
                                    "name": "places",
                                    "arguments": 'ery": "x"}',
                                },
                            }
                        ]
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        },
        {"choices": [], "usage": {"prompt_tokens": 50, "completion_tokens": 7}},
    ]
    body = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"

    def handler(request):
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(
            200, text=body, headers={"content-type": "text/event-stream"}
        )

    events = [
        e
        async for e in _llm(handler).stream(
            [{"role": "user", "content": "hi"}], purpose="test", tools=[TOOL]
        )
    ]
    assert [e.text for e in events if isinstance(e, TextDelta)] == ["Let me ", "check."]
    final = events[-1]
    assert isinstance(final, ChatResult)
    assert final.content == "Let me check."
    assert [(c.name, c.arguments) for c in final.tool_calls] == [
        ("search_places", {"query": "x"})
    ]
    [row] = await _calls()
    assert (row.input_tokens, row.output_tokens, row.status) == (50, 7, "ok")


async def test_missing_usage_is_estimated():
    def handler(request):
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "x" * 40}}]}
        )

    result = await _llm(handler, model="qwen2.5:3b").chat(
        [{"role": "user", "content": "y" * 400}], purpose="test"
    )
    assert result.usage.estimated
    [row] = await _calls()
    assert (row.input_tokens, row.output_tokens) == (100, 10)
    assert row.tokens_estimated
    assert float(row.list_cost_usd) == 0  # local model


async def test_malformed_tool_arguments_are_flagged_not_raised():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "c",
                                    "function": {"name": "f", "arguments": "{oops"},
                                }
                            ]
                        }
                    }
                ]
            },
        )

    result = await _llm(handler).chat([], purpose="test")
    call = result.tool_calls[0]
    assert not call.arguments_valid
    assert call.raw_arguments == "{oops"


async def test_rate_limit_and_errors_are_typed_and_logged():
    def limited(request):
        return httpx.Response(429, text="quota", headers={"retry-after": "12"})

    with pytest.raises(LLMRateLimited) as exc:
        await _llm(limited).chat([], purpose="test")
    assert exc.value.retry_after == 12

    def broken(request):
        return httpx.Response(500, text="boom")

    with pytest.raises(LLMError):
        await _llm(broken).chat([], purpose="test")

    def slow(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(LLMTimeout):
        await _llm(slow).chat([], purpose="test")

    rows = await _calls()
    assert [r.status for r in rows] == ["error"] * 3
    assert any("429" in r.error for r in rows)


async def test_stream_http_error_raises():
    def handler(request):
        return httpx.Response(429, text="slow down")

    with pytest.raises(LLMRateLimited):
        async for _ in _llm(handler).stream([], purpose="test"):
            pass


async def test_embedder_prefixes_truncates_and_normalizes():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        n = len(seen["body"]["input"])
        # A 6-dim model; we keep the first 4 dims and re-normalize.
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": i, "embedding": [3.0, 4.0, 0.0, 0.0, 9.0, 9.0]}
                    for i in range(n)
                ],
                "usage": {"prompt_tokens": 12},
            },
        )

    embedder = OpenAICompatEmbedder(
        base_url="http://llm.test/v1",
        api_key="",
        model="gemini-embedding-001",
        dim=4,
        query_prefix="q: ",
        doc_prefix="d: ",
        transport=httpx.MockTransport(handler),
    )
    [vec] = await embedder.embed(["wifi"], kind="query", purpose="test")
    assert seen["body"]["input"] == ["q: wifi"]
    assert vec == pytest.approx([0.6, 0.8, 0.0, 0.0])
    assert math.isclose(sum(x * x for x in vec), 1.0)

    await embedder.embed(["a", "b"], kind="document", purpose="test")
    assert seen["body"]["input"] == ["d: a", "d: b"]

    embedder.dim = 10
    with pytest.raises(LLMError, match="dimensions"):
        await embedder.embed(["a"], kind="query", purpose="test")

    rows = await _calls()
    assert [r.status for r in rows] == ["ok", "ok", "error"]


def test_price_lookup_uses_longest_prefix(monkeypatch):
    assert pricing.list_price("gemini-2.5-flash-lite-001") == (0.10, 0.40)
    assert pricing.list_price("models/gemini-2.5-flash") == (0.30, 2.50)
    assert pricing.list_price("llama3.1:8b") == (0.0, 0.0)

    monkeypatch.setattr(settings, "LLM_FREE_TIER", False)
    billed, listed = pricing.estimate_cost("gemini-2.5-flash", 1_000_000, 0)
    assert billed == listed == pytest.approx(0.30)


def test_price_overrides(monkeypatch):
    pricing._prices.cache_clear()
    monkeypatch.setattr(settings, "LLM_PRICES", '{"my-model": [1.0, 2.0]}')
    try:
        assert pricing.list_price("my-model") == (1.0, 2.0)
    finally:
        pricing._prices.cache_clear()
