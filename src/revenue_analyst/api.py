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

import json
import uuid
from datetime import date, datetime, timedelta

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command
from pydantic import BaseModel

from revenue_analyst.agents.pricing_review import (
    LAST_YEAR_SHIFT,
    PEER_WINDOW_DAYS,
    build_pricing_review,
    last_year_shift,
    night_outlook,
    pace_benchmark,
)
from revenue_analyst.agents.v1_react import build_agent
from revenue_analyst.agents.v3_deep import build_deep_agent
from revenue_analyst.analytics import (
    BookingPace,
    CalendarDay,
    PerformanceSummary,
    RoomTypeOccupancy,
    SeasonMonth,
    booking_pace,
    daily_calendar,
    performance_summary,
    room_type_occupancy,
    season_profile,
)
from revenue_analyst.config import Settings
from revenue_analyst.domain import Event, Property
from revenue_analyst.llm import message_text
from revenue_analyst.persistence import sqlite_checkpointer
from revenue_analyst.pms.mock import MockPMS
from revenue_analyst.pms.provider import PMSProvider, PropertyNotFoundError, RatePublisher


class PropertyInfo(BaseModel):
    property_id: str
    name: str
    city: str
    units: int
    as_of: datetime
    """The dataset's simulated "today" — the frontend anchors its views on it."""


class CalendarNight(CalendarDay):
    """A calendar day plus how it compares with similar nights last year
    (see pricing_review.night_outlook)."""

    kind: str
    peer_booked: float | None
    last_year_final: int
    status: str
    arrival_blocked: bool


class Benchmark(BaseModel):
    """The pricing review's pace rule for a window — no LLM."""

    basis: str
    on_the_books_share: float
    last_year_share_same_lead_time: float | None
    required_share: float
    behind: bool
    shift_days: int
    aligned_on: str | None


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    property_id: str | None = None
    """The property selected in the dashboard, injected as conversation
    context so "here" / "this property" resolve to it."""
    view_start: date | None = None
    view_end: date | None = None
    """The calendar month on screen (half-open), so "this month" resolves."""
    deep: bool = False
    """Route the message to the deep agent (lead plans and delegates to
    subagents) instead of the plain tool-calling agent."""


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
    target_days: list[str] | None = None
    """The dates the adjustment will touch (slow-pacing days only) — lets the
    UI preview the impact before approval."""
    outcome: str | None = None


def _chat_input(pms: PMSProvider, request: ChatRequest) -> str:
    """Prefix the user message with what the dashboard is showing (selected
    property, displayed calendar month), so "here" and "this month" resolve
    directly instead of triggering clarifications or full sweeps."""
    parts = []
    if request.property_id:
        try:
            prop = pms.get_property(request.property_id)
            parts.append(
                f"the user is currently viewing {prop.name} (property_id: "
                f"{prop.id}) — 'here' or 'this property' refers to it"
            )
        except PropertyNotFoundError:
            pass
    if request.view_start and request.view_end:
        parts.append(
            f"the calendar on screen shows {request.view_start.isoformat()} to "
            f"{request.view_end.isoformat()} (half-open) — 'this month' refers "
            f"to that window"
        )
    if not parts:
        return request.message
    return f"[Dashboard context: {'; '.join(parts)}.]\n\n{request.message}"


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
    if pms is None:
        from revenue_analyst.pms.factory import build_provider

        pms = build_provider(settings)

    # Stage 4: conversation memory lives in a LangGraph checkpointer (SQLite
    # by default), keyed by thread_id — it survives server restarts, unlike
    # Stage 3's in-process dict. Tests inject an InMemorySaver instead.
    checkpointer = checkpointer or sqlite_checkpointer(settings.state_dir)
    as_of = _resolve_as_of(pms)
    agent = build_agent(pms, as_of, model=model or settings.model, checkpointer=checkpointer)
    deep_agent = build_deep_agent(
        pms, as_of, model=model or settings.model, checkpointer=checkpointer
    )
    publisher = pms if settings.rate_publication and isinstance(pms, RatePublisher) else None
    review_workflow = build_pricing_review(
        pms, as_of, model=model or settings.model, checkpointer=checkpointer, publisher=publisher
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
            PropertyInfo(
                property_id=p.id, name=p.name, city=p.city, units=p.unit_count,
                as_of=_resolve_as_of(pms),
            )
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

    @app.post("/chat/stream")
    def chat_stream(request: ChatRequest):
        """Server-sent events: `tool` events as the agent picks tools, `token`
        events as the final answer is generated, then `done`. The non-streaming
        POST /chat stays for simple API clients."""
        from fastapi.responses import StreamingResponse

        chat_agent = deep_agent if request.deep else agent
        conversation_id = request.conversation_id or uuid.uuid4().hex
        config = {"configurable": {"thread_id": conversation_id}}

        def sse(payload: dict) -> str:
            return f"data: {json.dumps(payload)}\n\n"

        def events():
            yield sse({"type": "start", "conversation_id": conversation_id})
            stream = chat_agent.stream(
                {"messages": [HumanMessage(_chat_input(pms, request))]},
                config,
                stream_mode=["updates", "messages"],
            )
            for mode, payload in stream:
                if mode == "messages":
                    chunk, _meta = payload
                    # "messages" mode also yields ToolMessages; only LLM
                    # token chunks belong in the reply stream.
                    if not isinstance(chunk, AIMessageChunk):
                        continue
                    content = chunk.content
                    text = (
                        content
                        if isinstance(content, str)
                        else "".join(
                            block.get("text", "")
                            for block in content
                            if isinstance(block, dict)
                        )
                    )
                    if text:
                        yield sse({"type": "token", "text": text})
                else:
                    for node_output in payload.values():
                        for message in (node_output or {}).get("messages", []):
                            if isinstance(message, AIMessage):
                                for call in message.tool_calls:
                                    yield sse(
                                        {"type": "tool", "name": call["name"], "args": call["args"]}
                                    )
            yield sse({"type": "done"})

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.get("/properties/{property_id}/calendar")
    def property_calendar(property_id: str, start: date, end: date) -> list[CalendarNight]:
        prop = _property_or_404(property_id)
        _validate_range(start, end)
        if (end - start).days > 62:
            raise HTTPException(400, "request at most 62 days per call")
        rates = pms.get_daily_rates(property_id, start, end)
        days = daily_calendar(prop, pms.get_reservations(property_id, start, end), rates, start, end)
        # Night outlook: the window + 2 weeks ahead (minimum stays), and last
        # year ± the peer window.
        pad = timedelta(days=PEER_WINDOW_DAYS)
        ly_start, ly_end = start - LAST_YEAR_SHIFT - pad, end - LAST_YEAR_SHIFT + pad
        nights = night_outlook(
            prop,
            pms.get_reservations(property_id, start, end + timedelta(days=14)),
            pms.get_reservations(property_id, ly_start, ly_end),
            {r.day: r.min_stay for r in rates},
            pms.get_events(property_id, ly_start, end),
            _resolve_as_of(pms), start, end,
        )
        return [
            CalendarNight(
                **day.model_dump(), kind=n.kind, peer_booked=n.peer_booked,
                last_year_final=n.last_year_final, status=n.status,
                arrival_blocked=n.arrival_blocked,
            )
            for day, n in zip(days, nights, strict=True)
        ]

    @app.get("/properties/{property_id}/events")
    def property_events(property_id: str, start: date, end: date) -> list[Event]:
        _property_or_404(property_id)
        _validate_range(start, end)
        return pms.get_events(property_id, start, end)

    @app.get("/properties/{property_id}/benchmark")
    def property_benchmark(property_id: str, start: date, end: date) -> Benchmark:
        """On the books now vs the same window last year at the same lead
        time, aligned on the window's main event — the review's routing rule."""
        prop = _property_or_404(property_id)
        _validate_range(start, end)
        events = pms.get_events(property_id, start - timedelta(days=400), end)
        shift, aligned_on = last_year_shift(events, start, end)
        bench = pace_benchmark(
            prop,
            pms.get_reservations(property_id, start, end),
            pms.get_reservations(property_id, start - shift, end - shift),
            _resolve_as_of(pms), start, end, shift,
        )
        return Benchmark(**bench, shift_days=shift.days, aligned_on=aligned_on)

    @app.get("/properties/{property_id}/seasons")
    def property_seasons(property_id: str, year: int | None = None) -> list[SeasonMonth]:
        """Peak/high/shoulder/low per month from realized occupancy — by
        default last year's (the last complete year)."""
        prop = _property_or_404(property_id)
        year = year or _resolve_as_of(pms).year - 1
        reservations = pms.get_reservations(property_id, date(year, 1, 1), date(year + 1, 1, 1))
        return season_profile(prop, reservations, year)

    @app.get("/properties/{property_id}/room-types")
    def property_room_types(property_id: str, start: date, end: date) -> list[RoomTypeOccupancy]:
        prop = _property_or_404(property_id)
        _validate_range(start, end)
        reservations = pms.get_reservations(property_id, start, end)
        rates = pms.get_daily_rates(property_id, start, end)
        return room_type_occupancy(prop, reservations, rates, start, end)

    @app.post("/chat")
    def chat(request: ChatRequest) -> ChatResponse:
        chat_agent = deep_agent if request.deep else agent
        conversation_id = request.conversation_id or uuid.uuid4().hex
        config = {"configurable": {"thread_id": conversation_id}}
        previous = len(chat_agent.get_state(config).values.get("messages", []))
        result = chat_agent.invoke(
            {"messages": [HumanMessage(_chat_input(pms, request))]}, config
        )

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

    # Idempotency guard: one PENDING review per (property, window). Duplicate
    # POSTs (double-clicks, double-fired effects, retries) get the SAME
    # review back instead of a second approvable proposal — rate publication
    # must never be double-applied by transport noise.
    pending_reviews: dict[tuple, dict] = {}

    @app.post("/reviews")
    def start_review(request: ReviewRequest) -> ReviewResponse:
        _property_or_404(request.property_id)
        _validate_range(request.start, request.end)

        key = (request.property_id, request.start, request.end)
        existing = pending_reviews.get(key)
        if existing:
            state = review_workflow.get_state(
                {"configurable": {"thread_id": f"review-{existing['review_id']}"}}
            )
            if state.next:  # still waiting for a decision
                return ReviewResponse(status="pending_approval", **existing)
            del pending_reviews[key]

        review_id = uuid.uuid4().hex
        config = {"configurable": {"thread_id": f"review-{review_id}"}}
        result = review_workflow.invoke(
            {"property_id": request.property_id, "start": request.start, "end": request.end},
            config,
        )
        if "__interrupt__" in result:
            payload = result["__interrupt__"][0].value
            pending_reviews[key] = {
                "review_id": review_id,
                "proposal": payload["proposal"],
                "target_days": payload.get("target_days"),
            }
            return ReviewResponse(status="pending_approval", **pending_reviews[key])
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

    # --- web UI: the built React frontend, when present ----------------------
    dist = settings.frontend_dist
    if dist.is_dir():
        from fastapi.responses import RedirectResponse
        from fastapi.staticfiles import StaticFiles

        app.mount("/ui", StaticFiles(directory=dist, html=True), name="ui")

        @app.get("/", include_in_schema=False)
        def index() -> RedirectResponse:
            return RedirectResponse("/ui/")

    return app
