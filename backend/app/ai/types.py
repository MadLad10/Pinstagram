"""Provider-neutral types for chat and tool calling.

Messages use the OpenAI chat format (plain dicts), since every provider we
talk to (Ollama, Gemini, OpenAI, Groq) accepts it on its compatible endpoint.
"""

import json
from dataclasses import dataclass, field
from typing import Any

Message = dict[str, Any]


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON Schema for the arguments object

    def to_openai(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict
    # The raw JSON the model produced; kept so malformed arguments can be
    # reported back to it.
    raw_arguments: str = ""
    arguments_valid: bool = True


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    # True when the provider didn't report usage and we counted ~4 chars/token.
    estimated: bool = False


@dataclass
class ChatResult:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    finish_reason: str | None = None

    def as_message(self) -> Message:
        """The assistant turn to append to the history before tool results."""
        msg: Message = {"role": "assistant", "content": self.content or ""}
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": tc.raw_arguments or json.dumps(tc.arguments),
                    },
                }
                for tc in self.tool_calls
            ]
        return msg


@dataclass
class TextDelta:
    text: str


# A stream yields TextDelta chunks, then exactly one ChatResult.
StreamEvent = TextDelta | ChatResult


class LLMError(Exception):
    """The model call failed; safe to show a generic message to the user."""


class LLMRateLimited(LLMError):
    def __init__(self, message: str = "rate limited", retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class LLMTimeout(LLMError):
    pass


def parse_tool_arguments(call_id: str, name: str, raw: str | dict | None) -> ToolCall:
    if isinstance(raw, dict):  # some servers send an object, not a string
        return ToolCall(
            id=call_id, name=name, arguments=raw, raw_arguments=json.dumps(raw)
        )
    raw = raw or "{}"
    try:
        args = json.loads(raw)
        if not isinstance(args, dict):
            raise ValueError("arguments must be an object")
        return ToolCall(id=call_id, name=name, arguments=args, raw_arguments=raw)
    except ValueError:
        return ToolCall(
            id=call_id,
            name=name,
            arguments={},
            raw_arguments=raw,
            arguments_valid=False,
        )


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0
