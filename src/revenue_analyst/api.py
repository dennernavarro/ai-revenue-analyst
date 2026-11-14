"""Stage 3: the analyst as a service.

Two kinds of endpoints, on purpose:

- Plain REST (GET /properties, .../performance, .../pace): deterministic,
  fast, cheap — no LLM anywhere. Most of an "AI product" should live here.
- POST /chat: the single endpoint that talks to the agent.

The app is built by a factory so tests can inject a mock PMS or a scripted
fake model. Run it with:

    uv run uvicorn revenue_analyst.api:create_app --factory --reload
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel

from revenue_analyst.agents.v1_react import build_agent
from revenue_analyst.analytics import (
    BookingPace,
    PerformanceSummary,
    booking_pace,
    performance_summary,
)
from revenue_analyst.config import Settings
from revenue_analyst.domain import Property
from revenue_analyst.llm import message_text
from revenue_analyst.pms.mock import MockPMS
from revenue_analyst.pms.provider import PMSProvider, PropertyNotFoundError


class PropertyInfo(BaseModel):
    property_id: str
    name: str
    city: str
    units: int


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ToolCallInfo(BaseModel):
    name: str
    args: dict


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    tool_calls: list[ToolCallInfo]


def _resolve_as_of(pms: PMSProvider) -> datetime:
    """The mock datasets carry their own simulated "today"; real PMS data
    would use the wall clock."""
    if isinstance(pms, MockPMS):
        return pms.as_of(pms.list_properties()[0].id)
    return datetime.now()


def create_app(
    pms: PMSProvider | None = None,
    model: str | BaseChatModel | None = None,
) -> FastAPI:
    load_dotenv()
    settings = Settings()
    pms = pms or MockPMS(settings.data_dir)
    agent = build_agent(pms, _resolve_as_of(pms), model=model or settings.model)

    app = FastAPI(title="AI Revenue Analyst", version="0.1.0")

    # Stage 3 conversation memory: a dict in the process. Restarting the
    # server forgets everything — the limitation Stage 4's checkpointer fixes.
    conversations: dict[str, list[BaseMessage]] = {}

    def _property_or_404(property_id: str) -> Property:
        try:
            return pms.get_property(property_id)
        except PropertyNotFoundError:
            raise HTTPException(404, f"unknown property {property_id!r}") from None

    def _validate_range(start: date, end: date) -> None:
        if end <= start:
            raise HTTPException(400, "end must be after start (ranges are half-open)")

    @app.get("/properties")
    def list_properties() -> list[PropertyInfo]:
        return [
            PropertyInfo(property_id=p.id, name=p.name, city=p.city, units=p.unit_count)
            for p in pms.list_properties()
        ]

    @app.get("/properties/{property_id}/performance")
    def property_performance(property_id: str, start: date, end: date) -> PerformanceSummary:
        prop = _property_or_404(property_id)
        _validate_range(start, end)
        reservations = pms.get_reservations(property_id, start, end)
        return performance_summary(prop, reservations, start, end)

    @app.get("/properties/{property_id}/pace")
    def property_pace(property_id: str, start: date, end: date) -> BookingPace:
        prop = _property_or_404(property_id)
        _validate_range(start, end)
        reservations = pms.get_reservations(property_id, start, end)
        return booking_pace(prop, reservations, _resolve_as_of(pms), start, end)

    @app.post("/chat")
    def chat(request: ChatRequest) -> ChatResponse:
        conversation_id = request.conversation_id or uuid.uuid4().hex
        history = conversations.get(conversation_id, [])
        result = agent.invoke({"messages": [*history, HumanMessage(request.message)]})
        conversations[conversation_id] = result["messages"]

        new_messages = result["messages"][len(history) + 1 :]
        tool_calls = [
            ToolCallInfo(name=call["name"], args=call["args"])
            for message in new_messages
            if isinstance(message, AIMessage)
            for call in message.tool_calls
        ]
        return ChatResponse(
            conversation_id=conversation_id,
            reply=message_text(new_messages[-1]),
            tool_calls=tool_calls,
        )

    return app
