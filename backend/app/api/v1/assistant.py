import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select

from app.ai.agent import AgentEvent, run_agent
from app.core.config import settings
from app.core.deps import DB, CurrentUserID
from app.core.rate_limit import rate_limit
from app.models.llm_call import LLMCall
from app.services.directions_service import DHAKA_TZ

router = APIRouter(prefix="/assistant", tags=["assistant"])

MAX_HISTORY = 12


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class LatLng(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class ChatRequest(BaseModel):
    # The client keeps the conversation; older turns beyond MAX_HISTORY are dropped.
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    location: LatLng | None = None

    @model_validator(mode="after")
    def _ends_with_user(self) -> "ChatRequest":
        if self.messages[-1].role != "user":
            raise ValueError("the last message must be from the user")
        return self


async def _tokens_used_today(db, user_id) -> int:
    midnight = datetime.now(DHAKA_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return await db.scalar(
        select(
            func.coalesce(func.sum(LLMCall.input_tokens + LLMCall.output_tokens), 0)
        ).where(
            LLMCall.user_id == user_id,
            LLMCall.purpose == "assistant",
            LLMCall.created_at >= midnight,
        )
    )


async def _sse(events: AsyncIterator[AgentEvent]) -> AsyncIterator[str]:
    async for event in events:
        data = json.dumps(event.data, ensure_ascii=False, default=str)
        yield f"event: {event.type}\ndata: {data}\n\n"


@router.post(
    "/chat",
    dependencies=[
        Depends(rate_limit("assistant", 10, 60, per="user")),
        Depends(rate_limit("assistant_day", 200, 24 * 3600, per="user")),
    ],
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def chat(body: ChatRequest, user_id: CurrentUserID, db: DB):
    """Trip-planning chat, streamed as Server-Sent Events.

    Events: `token` {text}, `tool_call` {id, name, arguments}, `tool_result`
    {id, name, ok, summary}, `sources` {places, routes}, `error` {code,
    message}, and finally `done` {finish_reason, steps, tool_calls, grounding}.
    """
    if not settings.AI_ENABLED:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="The assistant is turned off"
        )
    if settings.ASSISTANT_DAILY_TOKENS and (
        await _tokens_used_today(db, user_id) >= settings.ASSISTANT_DAILY_TOKENS
    ):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily assistant limit reached. It resets at midnight.",
        )

    history = [m.model_dump() for m in body.messages[-MAX_HISTORY:]]
    location = (body.location.lat, body.location.lng) if body.location else None
    return StreamingResponse(
        _sse(run_agent(history, user_id=user_id, user_location=location)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
