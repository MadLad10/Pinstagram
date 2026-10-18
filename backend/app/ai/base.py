"""Provider interfaces. Subclasses implement `_chat`/`_stream`/`_embed`; the
public methods here time and log every call (see `telemetry`)."""

import asyncio
import math
import time
import uuid
from abc import ABC, abstractmethod
from collections import OrderedDict
from collections.abc import AsyncIterator
from typing import Literal

from app.ai import telemetry
from app.ai.types import (
    ChatResult,
    LLMError,
    Message,
    StreamEvent,
    ToolSpec,
    Usage,
    estimate_tokens,
)


class LLMProvider(ABC):
    provider: str
    model: str

    async def chat(
        self,
        messages: list[Message],
        *,
        purpose: str,
        tools: list[ToolSpec] | None = None,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        user_id: uuid.UUID | None = None,
    ) -> ChatResult:
        start = time.perf_counter()
        try:
            result = await self._chat(
                messages,
                tools=tools,
                json_mode=json_mode,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            await self._log(purpose, user_id, start, Usage(), "error", exc)
            raise
        await self._log(purpose, user_id, start, result.usage, "ok", model=result.model)
        return result

    async def stream(
        self,
        messages: list[Message],
        *,
        purpose: str,
        tools: list[ToolSpec] | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        user_id: uuid.UUID | None = None,
    ) -> AsyncIterator[StreamEvent]:
        start = time.perf_counter()
        final: ChatResult | None = None
        streamed: list[str] = []
        try:
            async for event in self._stream(
                messages, tools=tools, temperature=temperature, max_tokens=max_tokens
            ):
                if isinstance(event, ChatResult):
                    final = event
                else:
                    streamed.append(event.text)
                yield event
        except (GeneratorExit, asyncio.CancelledError):
            # The client went away mid-stream. Awaiting here could be cancelled
            # again, so log in the background.
            usage = Usage(
                output_tokens=estimate_tokens("".join(streamed)), estimated=True
            )
            asyncio.ensure_future(
                self._log(purpose, user_id, start, usage, "cancelled")
            )
            raise
        except Exception as exc:
            await self._log(purpose, user_id, start, Usage(), "error", exc)
            raise
        if final is None:
            await self._log(
                purpose, user_id, start, Usage(), "error", "no final result"
            )
            raise LLMError("stream ended without a result")
        await self._log(purpose, user_id, start, final.usage, "ok", model=final.model)

    @abstractmethod
    async def _chat(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None,
        json_mode: bool,
        temperature: float,
        max_tokens: int | None,
    ) -> ChatResult: ...

    @abstractmethod
    def _stream(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None,
        temperature: float,
        max_tokens: int | None,
    ) -> AsyncIterator[StreamEvent]: ...

    async def _log(
        self, purpose, user_id, start, usage, status, error=None, model=None
    ):
        await telemetry.record_call(
            purpose=purpose,
            provider=self.provider,
            model=model or self.model,
            user_id=user_id,
            usage=usage,
            latency_ms=int((time.perf_counter() - start) * 1000),
            status=status,
            error=error,
        )


class EmbeddingProvider(ABC):
    provider: str
    model: str
    dim: int
    batch_size = 64
    # Similarity below this is noise for this model (see EMBEDDING_MIN_SIMILARITY).
    min_similarity = 0.0

    query_cache_size = 256

    def __init__(self, query_prefix: str = "", doc_prefix: str = ""):
        self.query_prefix = query_prefix
        self.doc_prefix = doc_prefix
        self._query_cache: OrderedDict[str, list[float]] = OrderedDict()

    async def embed_query(
        self, text: str, *, purpose: str, user_id: uuid.UUID | None = None
    ) -> list[float]:
        """Embed a search query, with a small LRU cache: popular queries cost
        nothing, which matters on rate-limited free tiers."""
        key = " ".join(text.lower().split())
        if key in self._query_cache:
            self._query_cache.move_to_end(key)
            return self._query_cache[key]
        [vector] = await self.embed(
            [text], kind="query", purpose=purpose, user_id=user_id
        )
        self._query_cache[key] = vector
        if len(self._query_cache) > self.query_cache_size:
            self._query_cache.popitem(last=False)
        return vector

    async def embed(
        self,
        texts: list[str],
        *,
        kind: Literal["query", "document"],
        purpose: str,
        user_id: uuid.UUID | None = None,
    ) -> list[list[float]]:
        """Unit-length vectors of exactly `dim` dimensions, one per text."""
        if not texts:
            return []
        prefix = self.query_prefix if kind == "query" else self.doc_prefix
        vectors: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = [prefix + t for t in texts[i : i + self.batch_size]]
            start = time.perf_counter()
            try:
                raw, usage = await self._embed(batch)
                if len(raw) != len(batch):
                    raise LLMError(f"expected {len(batch)} embeddings, got {len(raw)}")
                vectors.extend(self._fit(v) for v in raw)
            except Exception as exc:
                await self._log(purpose, user_id, start, Usage(), "error", exc)
                raise
            await self._log(purpose, user_id, start, usage, "ok")
        return vectors

    def _fit(self, vector: list[float]) -> list[float]:
        if len(vector) < self.dim:
            raise LLMError(
                f"{self.model} returned {len(vector)} dimensions, need {self.dim}"
            )
        vector = vector[: self.dim]
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return [x / norm for x in vector]

    @abstractmethod
    async def _embed(self, texts: list[str]) -> tuple[list[list[float]], Usage]: ...

    async def _log(self, purpose, user_id, start, usage, status, error=None):
        await telemetry.record_call(
            purpose=purpose,
            provider=self.provider,
            model=self.model,
            user_id=user_id,
            usage=usage,
            latency_ms=int((time.perf_counter() - start) * 1000),
            status=status,
            error=error,
        )
