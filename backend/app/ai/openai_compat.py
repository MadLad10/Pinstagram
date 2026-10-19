"""Chat and embeddings over the OpenAI-compatible HTTP API.

Covers Ollama (`http://localhost:11434/v1`), Gemini
(`https://generativelanguage.googleapis.com/v1beta/openai`), OpenAI, Groq and
OpenRouter with no SDK dependency.
"""

import json
from collections.abc import AsyncIterator

import httpx

from app.ai.base import EmbeddingProvider, LLMProvider
from app.ai.types import (
    ChatResult,
    LLMError,
    LLMRateLimited,
    LLMTimeout,
    Message,
    StreamEvent,
    TextDelta,
    ToolSpec,
    Usage,
    estimate_tokens,
    parse_tool_arguments,
)


def _headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code < 400:
        return
    body = resp.text[:300]
    if resp.status_code == 429:
        retry_after = resp.headers.get("retry-after")
        raise LLMRateLimited(
            f"HTTP 429: {body}",
            retry_after=float(retry_after)
            if retry_after and retry_after.isdigit()
            else None,
        )
    raise LLMError(f"HTTP {resp.status_code}: {body}")


def _usage(raw: dict | None, messages: list[Message], output: str) -> Usage:
    if raw and raw.get("prompt_tokens") is not None:
        return Usage(
            input_tokens=raw.get("prompt_tokens") or 0,
            output_tokens=raw.get("completion_tokens") or 0,
        )
    prompt = "".join(str(m.get("content") or "") for m in messages)
    return Usage(
        input_tokens=estimate_tokens(prompt),
        output_tokens=estimate_tokens(output),
        estimated=True,
    )


class OpenAICompatLLM(LLMProvider):
    provider = "openai_compat"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.transport = transport  # injectable for tests

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout, transport=self.transport)

    def _payload(self, messages, tools, temperature, max_tokens, **extra) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            **extra,
        }
        if tools:
            payload["tools"] = [t.to_openai() for t in tools]
        if max_tokens:
            payload["max_tokens"] = max_tokens
        return payload

    async def _chat(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None,
        json_mode: bool,
        temperature: float,
        max_tokens: int | None,
    ) -> ChatResult:
        extra = {"response_format": {"type": "json_object"}} if json_mode else {}
        payload = self._payload(messages, tools, temperature, max_tokens, **extra)
        try:
            async with self._client() as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=_headers(self.api_key),
                )
        except httpx.TimeoutException as exc:
            raise LLMTimeout(str(exc) or "timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"{type(exc).__name__}: {exc}") from exc
        _raise_for_status(resp)

        try:
            data = resp.json()
            choice = data["choices"][0]
            message = choice["message"]
        except (ValueError, KeyError, IndexError) as exc:
            raise LLMError(f"unexpected response: {resp.text[:300]}") from exc
        content = message.get("content") or ""
        tool_calls = [
            parse_tool_arguments(
                tc.get("id") or f"call_{i}",
                tc["function"]["name"],
                tc["function"].get("arguments"),
                tc.get("extra_content"),
            )
            for i, tc in enumerate(message.get("tool_calls") or [])
        ]
        return ChatResult(
            content=content,
            tool_calls=tool_calls,
            usage=_usage(data.get("usage"), messages, content),
            model=data.get("model") or self.model,
            finish_reason=choice.get("finish_reason"),
        )

    async def _stream(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None,
        temperature: float,
        max_tokens: int | None,
    ) -> AsyncIterator[StreamEvent]:
        payload = self._payload(
            messages,
            tools,
            temperature,
            max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )
        content: list[str] = []
        calls: dict[int, dict] = {}
        usage_raw = None
        finish_reason = None
        model = self.model
        try:
            async with self._client() as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=_headers(self.api_key),
                ) as resp:
                    if resp.status_code >= 400:
                        await resp.aread()
                        _raise_for_status(resp)
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except ValueError:
                            continue
                        model = chunk.get("model") or model
                        if chunk.get("usage"):
                            usage_raw = chunk["usage"]
                        for choice in chunk.get("choices") or []:
                            delta = choice.get("delta") or {}
                            if text := delta.get("content"):
                                content.append(text)
                                yield TextDelta(text)
                            # Tool calls arrive in fragments keyed by index;
                            # some servers send each call whole and omit it.
                            for pos, frag in enumerate(delta.get("tool_calls") or []):
                                slot = calls.setdefault(
                                    frag.get("index", pos),
                                    {"id": "", "name": "", "arguments": ""},
                                )
                                slot["id"] = frag.get("id") or slot["id"]
                                if frag.get("extra_content"):
                                    slot["extra_content"] = frag["extra_content"]
                                fn = frag.get("function") or {}
                                slot["name"] += fn.get("name") or ""
                                args = fn.get("arguments")
                                if isinstance(args, dict):
                                    args = json.dumps(args)
                                slot["arguments"] += args or ""
                            finish_reason = choice.get("finish_reason") or finish_reason
        except httpx.TimeoutException as exc:
            raise LLMTimeout(str(exc) or "timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"{type(exc).__name__}: {exc}") from exc

        text = "".join(content)
        yield ChatResult(
            content=text,
            tool_calls=[
                parse_tool_arguments(
                    c["id"] or f"call_{i}",
                    c["name"],
                    c["arguments"],
                    c.get("extra_content"),
                )
                for i, c in sorted(calls.items())
            ],
            usage=_usage(usage_raw, messages, text),
            model=model,
            finish_reason=finish_reason,
        )


class OpenAICompatEmbedder(EmbeddingProvider):
    provider = "openai_compat"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        dim: int,
        timeout: float = 30,
        query_prefix: str = "",
        doc_prefix: str = "",
        min_similarity: float = 0.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        super().__init__(query_prefix=query_prefix, doc_prefix=doc_prefix)
        self.min_similarity = min_similarity
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.dim = dim
        self.timeout = timeout
        self.transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout, transport=self.transport)

    async def _embed(self, texts: list[str]) -> tuple[list[list[float]], Usage]:
        try:
            async with self._client() as client:
                resp = await client.post(
                    f"{self.base_url}/embeddings",
                    json={"model": self.model, "input": texts},
                    headers=_headers(self.api_key),
                )
        except httpx.TimeoutException as exc:
            raise LLMTimeout(str(exc) or "timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"{type(exc).__name__}: {exc}") from exc
        _raise_for_status(resp)
        try:
            data = resp.json()
            rows = sorted(data["data"], key=lambda d: d.get("index", 0))
            vectors = [row["embedding"] for row in rows]
        except (ValueError, KeyError, TypeError) as exc:
            raise LLMError(f"unexpected response: {resp.text[:300]}") from exc
        raw = data.get("usage") or {}
        if raw.get("prompt_tokens") is not None:
            usage = Usage(input_tokens=raw["prompt_tokens"])
        else:
            usage = Usage(input_tokens=sum(map(estimate_tokens, texts)), estimated=True)
        return vectors, usage
