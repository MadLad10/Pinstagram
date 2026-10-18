"""Deterministic stand-ins for tests and offline evaluation. No network."""

import hashlib
import math
import re
from collections import deque
from collections.abc import AsyncIterator, Callable

from app.ai.base import EmbeddingProvider, LLMProvider
from app.ai.types import (
    ChatResult,
    LLMError,
    Message,
    StreamEvent,
    TextDelta,
    ToolCall,
    ToolSpec,
    Usage,
    estimate_tokens,
)

Responder = Callable[[list[Message], list[ToolSpec] | None], ChatResult | str]


def text_reply(content: str) -> ChatResult:
    return ChatResult(content=content, model="fake-llm", finish_reason="stop")


def tool_reply(*calls: tuple[str, dict], content: str = "") -> ChatResult:
    return ChatResult(
        content=content,
        tool_calls=[
            ToolCall(id=f"call_{i}", name=name, arguments=args)
            for i, (name, args) in enumerate(calls)
        ],
        model="fake-llm",
        finish_reason="tool_calls",
    )


class FakeLLM(LLMProvider):
    """Replies from a queue of scripted results, or from a responder function.

    Every request is recorded in `requests` so tests can assert on prompts and
    on the tool results the model was shown.
    """

    provider = "fake"
    model = "fake-llm"

    def __init__(self, *replies: ChatResult | str, responder: Responder | None = None):
        self.replies: deque[ChatResult | str] = deque(replies)
        self.responder = responder
        self.requests: list[dict] = []
        self.error: Exception | None = None

    def queue(self, *replies: ChatResult | str) -> None:
        self.replies.extend(replies)

    def _next(self, messages: list[Message], tools, **kwargs) -> ChatResult:
        self.requests.append({"messages": list(messages), "tools": tools, **kwargs})
        if self.error:
            raise self.error
        if self.replies:
            reply = self.replies.popleft()
        elif self.responder:
            reply = self.responder(messages, tools)
        else:
            raise LLMError("FakeLLM has no scripted reply left")
        result = text_reply(reply) if isinstance(reply, str) else reply
        prompt = "".join(str(m.get("content") or "") for m in messages)
        result.usage = Usage(
            input_tokens=estimate_tokens(prompt),
            output_tokens=estimate_tokens(result.content),
        )
        return result

    async def _chat(self, messages, *, tools, json_mode, temperature, max_tokens):
        return self._next(messages, tools, json_mode=json_mode)

    async def _stream(
        self, messages, *, tools, temperature, max_tokens
    ) -> AsyncIterator[StreamEvent]:
        result = self._next(messages, tools, stream=True)
        for word in re.findall(r"\S+\s*", result.content):
            yield TextDelta(word)
        yield result


_STOPWORDS = {
    "a", "an", "and", "the", "in", "on", "at", "of", "to", "for", "with", "is",
    "it", "was", "are", "be", "this", "that", "my", "i", "we", "you", "very",
    "near", "good", "great", "place", "spot",
}  # fmt: skip


def _tokens(text: str) -> list[str]:
    out = []
    for tok in re.findall(r"\w+", text.lower()):
        if tok in _STOPWORDS:
            continue
        if len(tok) > 3 and tok.endswith("s"):  # crude plural folding
            tok = tok[:-1]
        out.append(tok)
    return out


class FakeEmbedder(EmbeddingProvider):
    """Feature-hashed bag of words: texts sharing words get similar vectors,
    which is enough to exercise retrieval and ranking deterministically."""

    provider = "fake"
    model = "fake-embed"
    # Word-overlap cosine: unrelated texts sit near 0, related ones above ~0.2.
    min_similarity = 0.15

    def __init__(self, dim: int = 768):
        super().__init__()
        self.dim = dim
        self.calls: list[list[str]] = []
        self.error: Exception | None = None

    async def _embed(self, texts: list[str]) -> tuple[list[list[float]], Usage]:
        self.calls.append(list(texts))
        if self.error:
            raise self.error
        vectors = []
        for text in texts:
            vec = [0.0] * self.dim
            for tok in _tokens(text):
                h = int.from_bytes(
                    hashlib.blake2b(tok.encode(), digest_size=8).digest()
                )
                vec[h % self.dim] += 1.0 if (h >> 32) & 1 else -1.0
            if not any(vec):
                vec[0] = 1.0  # avoid a zero vector, whose cosine distance is NaN
            norm = math.sqrt(sum(x * x for x in vec))
            vectors.append([x / norm for x in vec])
        usage = Usage(input_tokens=sum(map(estimate_tokens, texts)))
        return vectors, usage
