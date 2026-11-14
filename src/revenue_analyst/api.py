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
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command
from pydantic import BaseModel

from revenue_analyst.agents.pricing_review import build_pricing_review
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
from revenue_analyst.persistence import sqlite_checkpointer
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


class ReviewRequest(BaseModel):
    property_id: str
    start: date
    end: date


class ReviewDecision(BaseModel):
    approved: bool
    note: str = ""


class ReviewResponse(BaseModel):
    review_id: str
    status: str
    """"pending_approval", "no_action" or "completed"."""
    proposal: dict | None = None
    outcome: str | None = None


def _resolve_as_of(pms: PMSProvider) -> datetime:
    """The mock datasets carry their own simulated "today"; real PMS data
    would use the wall clock."""
    if isinstance(pms, MockPMS):
        return pms.as_of(pms.list_properties()[0].id)
    return datetime.now()


def create_app(
    pms: PMSProvider | None = None,
    model: str | BaseChatModel | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
) -> FastAPI:
    load_dotenv()
    settings = Settings()
    pms = pms or MockPMS(settings.data_dir)

    # Stage 4: conversation memory lives in a LangGraph checkpointer (SQLite
    # by default), keyed by thread_id — it survives server restarts, unlike
    # Stage 3's in-process dict. Tests inject an InMemorySaver instead.
    checkpointer = checkpointer or sqlite_checkpointer(settings.state_dir)
    as_of = _resolve_as_of(pms)
    agent = build_agent(pms, as_of, model=model or settings.model, checkpointer=checkpointer)
    review_workflow = build_pricing_review(
        pms, as_of, model=model or settings.model, checkpointer=checkpointer
    )

    app = FastAPI(title="AI Revenue Analyst", version="0.1.0")

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
        config = {"configurable": {"thread_id": conversation_id}}
        previous = len(agent.get_state(config).values.get("messages", []))
        result = agent.invoke({"messages": [HumanMessage(request.message)]}, config)

        new_messages = result["messages"][previous + 1 :]
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

    # --- Stage 5: human-in-the-loop pricing reviews over HTTP ----------------
    # The interrupt pattern maps cleanly to REST: starting a review either
    # finishes (healthy pace) or parks a paused graph in the checkpointer;
    # the decision endpoint resumes it — possibly days later, from another
    # process.

    @app.post("/reviews")
    def start_review(request: ReviewRequest) -> ReviewResponse:
        _property_or_404(request.property_id)
        _validate_range(request.start, request.end)
        review_id = uuid.uuid4().hex
        config = {"configurable": {"thread_id": f"review-{review_id}"}}
        result = review_workflow.invoke(
            {"property_id": request.property_id, "start": request.start, "end": request.end},
            config,
        )
        if "__interrupt__" in result:
            return ReviewResponse(
                review_id=review_id,
                status="pending_approval",
                proposal=result["__interrupt__"][0].value["proposal"],
            )
        return ReviewResponse(review_id=review_id, status="no_action", outcome=result["outcome"])

    @app.post("/reviews/{review_id}/decision")
    def decide_review(review_id: str, decision: ReviewDecision) -> ReviewResponse:
        config = {"configurable": {"thread_id": f"review-{review_id}"}}
        state = review_workflow.get_state(config)
        if not state.values:
            raise HTTPException(404, f"unknown review {review_id!r}")
        if not state.next:
            raise HTTPException(409, "this review is not awaiting a decision")
        result = review_workflow.invoke(
            Command(resume={"approved": decision.approved, "note": decision.note}), config
        )
        return ReviewResponse(review_id=review_id, status="completed", outcome=result["outcome"])

    return app
