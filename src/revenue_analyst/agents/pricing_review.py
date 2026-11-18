"""Stage 5: a pricing-review WORKFLOW — deterministic control flow with one
LLM slot inside, and a human approval gate.

The chat agent lets the model drive. Here the shape is inverted: the
graph drives, and the model fills one well-defined slot.

    START → analyze (deterministic)
              ├─ healthy pace → summarize (deterministic) → END
              └─ weak pace   → propose (LLM, structured output)
                                → enforce_constraints (deterministic clamp)
                                → human_approval (interrupt: the graph PAUSES)
                                → record → END

Lessons baked in:

- Custom state beyond messages: a TypedDict the nodes fill field by field.
- The routing decision (healthy vs weak pace) is a rule in Python, not a
  judgment call delegated to the LLM: on-the-books vs the same window last
  year at the same lead time, so a quiet low season isn't mistaken for
  weak pace (fixed threshold only when there is no history).
- model.with_structured_output(RateProposal): the LLM's slot has a schema,
  not free text.
- Hard business constraints live OUTSIDE the model: the clamp node caps any
  proposal at ±MAX_ADJUSTMENT_PCT no matter what the LLM says.
- interrupt() turns the paused graph into a checkpoint, which is why the
  approval can arrive seconds later (CLI) or days later (API, another
  process) — a checkpointer is therefore required.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from statistics import mean
from typing import TypedDict

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from revenue_analyst.analytics import (
    booking_pace,
    daily_calendar,
    on_the_books_nights,
    performance_summary,
)
from revenue_analyst.domain import Event, Property, Reservation, ReservationStatus
from revenue_analyst.llm import init_model
from revenue_analyst.pms.provider import PMSProvider, RatePublisher

LAST_YEAR_SHIFT = timedelta(days=364)
"""52 weeks back, so weekdays align (a Saturday compares with a Saturday)."""

PACE_TOLERANCE = 0.90
"""A window (or day) is behind when its on-the-books is below 90% of what the
same window had on the books at the same lead time last year."""

HEALTHY_OTB_SHARE = 0.40
"""Fallback only, when the PMS has no last-year history for the window:
on-the-books share of capacity above which no action is proposed."""

MAX_ADJUSTMENT_PCT = 25.0
"""Business policy: no single adjustment beyond ±25%, enforced in code."""

PEER_WINDOW_DAYS = 7
"""Night-level check: compare with last year's nights of the same kind within
±7 days — pooling gives enough signal even for a one-unit villa."""

MIN_PEER_SHARE = 0.25
"""Below this (similar nights last year had < 25% booked by now) a night is
"too early to tell" rather than behind."""


class NightOutlook(BaseModel):
    """One night vs similar nights last year — information only; nothing acts
    on it yet (Auto-pilot will, once the night-level backtest backs it)."""

    day: date
    kind: str
    """"event", "weekend" (Fri/Sat nights) or "weekday"."""
    booked_now: int
    peer_booked: float | None
    """Average nights on the books at this lead time on similar nights last
    year (same kind, ±PEER_WINDOW_DAYS); None without history."""
    last_year_final: int
    """Confirmed nights sold on the same weekday last year (`shift` back)."""
    status: str
    """"sold_out", "behind", "on_track", "too_early" or "no_history"."""
    arrival_blocked: bool
    """True when nobody can check in: the night has a free unit, but its
    minimum stay runs into a sold-out night."""


def _night_kind(day: date, events: list[Event]) -> str:
    if any(e.start <= day < e.end for e in events):
        return "event"
    return "weekend" if day.weekday() in (4, 5) else "weekday"


def _sold(reservations: list[Reservation], night: date) -> int:
    return sum(
        1 for r in reservations
        if r.status is ReservationStatus.CONFIRMED and r.check_in <= night < r.check_out
    )


def night_outlook(
    prop: Property,
    reservations: list[Reservation],
    ly_reservations: list[Reservation],
    min_stays: dict[date, int],
    events: list[Event],
    as_of: datetime,
    start: date,
    end: date,
    shift: timedelta = LAST_YEAR_SHIFT,
) -> list[NightOutlook]:
    """Per-night outlook for [start, end).

    `reservations` must cover the window plus the longest minimum stay after
    it; `ly_reservations` and `events` must cover the window `shift` back,
    ±PEER_WINDOW_DAYS.
    """
    units = prop.unit_count
    ly_as_of = as_of - shift
    one = timedelta(days=1)

    def booked(night: date) -> int:
        return on_the_books_nights(reservations, as_of, night, night + one)

    nights = []
    day = start
    while day < end:
        kind = _night_kind(day, events)
        now = booked(day)
        peers = [
            on_the_books_nights(ly_reservations, ly_as_of, q, q + one)
            for q in (day - shift + timedelta(days=o)
                      for o in range(-PEER_WINDOW_DAYS, PEER_WINDOW_DAYS + 1))
            if _night_kind(q, events) == kind
        ]
        peer = sum(peers) / len(peers) if ly_reservations and peers else None
        if now >= units:
            status = "sold_out"
        elif peer is None:
            status = "no_history"
        elif peer < MIN_PEER_SHARE * units:
            status = "too_early"
        elif now < PACE_TOLERANCE * peer:
            status = "behind"
        else:
            status = "on_track"
        stay = min_stays.get(day, 1)
        blocked = now < units and any(
            booked(day + timedelta(days=k)) >= units for k in range(1, stay)
        )
        nights.append(
            NightOutlook(
                day=day, kind=kind, booked_now=now,
                peer_booked=round(peer, 2) if peer is not None else None,
                last_year_final=_sold(ly_reservations, day - shift),
                status=status, arrival_blocked=blocked,
            )
        )
        day += one
    return nights


def last_year_shift(events: list[Event], start: date, end: date) -> tuple[timedelta, str | None]:
    """How far back "the same window last year" is, and which event aligned it.

    Default: 364 days (weekdays align). When the window holds an event, shift
    instead to that event's previous edition, rounded to whole weeks — Easter
    and Thanksgiving land exactly on last year's, fixed-date holidays like
    Christmas round back to 364 so weekdays still align. With several events,
    the one with the strongest impact (either direction) decides.
    `events` must reach back ~13 months before `start` to find the editions.
    """
    inside = [e for e in events if start <= e.start < end]
    if not inside:
        return LAST_YEAR_SHIFT, None
    main = max(inside, key=lambda e: abs(e.impact - 1))
    earlier = [
        e for e in events
        if e.name == main.name and e.start <= main.start - timedelta(days=300)
    ]
    if not earlier:
        return LAST_YEAR_SHIFT, None
    days = (main.start - max(earlier, key=lambda e: e.start).start).days
    return timedelta(weeks=round(days / 7)), main.name


def pace_benchmark(
    prop: Property,
    reservations: list[Reservation],
    ly_reservations: list[Reservation],
    as_of: datetime,
    start: date,
    end: date,
    ly_shift: timedelta = LAST_YEAR_SHIFT,
) -> dict:
    """Is [start, end) pacing behind? The routing rule of the review, kept pure
    so the backtest replays exactly what the workflow decides.

    Benchmark: what the same window (`ly_shift` earlier, see last_year_shift)
    had on the books at the same lead time, minus PACE_TOLERANCE — seasonality
    comes for free. Pass `ly_reservations=[]` (no history) to get the
    fixed-threshold fallback.
    """
    capacity = prop.unit_count * (end - start).days
    has_history = bool(ly_reservations)
    otb_now = on_the_books_nights(reservations, as_of, start, end)
    otb_ly = on_the_books_nights(ly_reservations, as_of - ly_shift, start - ly_shift, end - ly_shift)
    required = otb_ly * PACE_TOLERANCE / capacity if has_history else HEALTHY_OTB_SHARE
    return {
        "basis": "last_year_same_lead_time" if has_history else "fixed_threshold",
        "on_the_books_share": round(otb_now / capacity, 4),
        "last_year_share_same_lead_time": round(otb_ly / capacity, 4) if has_history else None,
        "required_share": round(required, 4),
        "behind": otb_now / capacity < required,
    }


class RateProposal(BaseModel):
    adjustment_pct: float = Field(
        description="Percent change to published nightly rates, e.g. -10 for a 10% discount."
    )
    rationale: str = Field(description="Why this adjustment, grounded in the analysis numbers.")
    expected_effect: str = Field(description="Expected effect on occupancy and revenue.")


class ReviewState(TypedDict, total=False):
    property_id: str
    start: date
    end: date
    analysis: dict
    proposal: dict
    """A RateProposal dump. Checkpointed state should hold plain-serializable
    data, not custom classes — the checkpointer warns (soon: refuses) when
    deserializing arbitrary types."""
    decision: dict
    outcome: str


PROPOSE_PROMPT = """\
You are a revenue analyst. A future stay window is pacing behind its
benchmark ("pace_benchmark": normally the same window last year at the same
lead time). Based ONLY on the analysis below (JSON), propose ONE rate
adjustment within ±{max_pct}% and justify it with those numbers.
"same_window_last_year" (final results) and the benchmark both look back by
"last_year_alignment.shift_days": 364 so weekdays align, or whole weeks to
the previous edition of the event in the window (e.g. Easter). "events" lists
the holidays and local events in the window with their demand impact (1.0
neutral) — use them to explain why dates are strong or weak.

Respect "rate_limits": published rates can never leave that band, so if
current rates are already close to the floor, propose only the small cut that
still fits (or focus the rationale on non-price levers) — repeated deep
discounts on already-discounted rates destroy revenue.

Your adjustment will be applied ONLY to the dates in
"day_targeting.target_days" (those filled below "pace_benchmark.required_share"); dates already
selling well keep their price, so reason about those slow dates.

{analysis}
"""


def build_pricing_review(
    pms: PMSProvider,
    as_of: datetime,
    model: str | BaseChatModel = "openrouter:openai/gpt-4o-mini",
    checkpointer: BaseCheckpointSaver | None = None,
    publisher: RatePublisher | None = None,
):
    if checkpointer is None:
        raise ValueError("the pricing review pauses on interrupt(), so it needs a checkpointer")
    if isinstance(model, str):
        model = init_model(model)
    proposer = model.with_structured_output(RateProposal)

    def analyze(state: ReviewState) -> dict:
        prop = pms.get_property(state["property_id"])
        start, end = state["start"], state["end"]

        reservations = pms.get_reservations(prop.id, start, end)
        pace = booking_pace(prop, reservations, as_of, start, end)
        rates = pms.get_daily_rates(prop.id, start, end)
        events = pms.get_events(prop.id, start - timedelta(days=400), end)
        shift, aligned_on = last_year_shift(events, start, end)
        ly_start, ly_end = start - shift, end - shift
        ly_reservations = pms.get_reservations(prop.id, ly_start, ly_end)
        last_year = performance_summary(prop, ly_reservations, ly_start, ly_end)
        bench = pace_benchmark(prop, reservations, ly_reservations, as_of, start, end, shift)

        avg_rate = round(mean(r.rate for r in rates), 2) if rates else 0.0
        # Discounts are exhausted once the average sits at (or within 2% of)
        # the property's hard floor — a deterministic fact, not a judgment.
        floor_reached = bool(rates) and avg_rate <= prop.min_rate * 1.02

        # Day-level targeting: an adjustment only makes sense on dates filled
        # BELOW the window's benchmark share. Dates selling above it — or
        # sold out — keep their price; discounting them burns revenue.
        # ponytail: one benchmark per window; a per-day last-year comparison is
        # too sparse for small inventory (a 1-unit villa is 0 or 1 per day).
        # Upgrade with multi-year history or holiday-aligned day matching.
        calendar = daily_calendar(prop, reservations, rates, start, end)
        target_days = [
            d.day.isoformat()
            for d in calendar
            if d.capacity and d.nights_sold / d.capacity < bench["required_share"]
        ]

        return {
            "analysis": {
                "window": {"start": start.isoformat(), "end": end.isoformat()},
                "pace": pace.model_dump(mode="json"),
                "published_rates": {
                    "min": min(r.rate for r in rates),
                    "avg": avg_rate,
                    "max": max(r.rate for r in rates),
                }
                if rates
                else None,
                "rate_limits": {"min": prop.min_rate, "max": prop.max_rate},
                "rate_floor_reached": floor_reached,
                "pace_benchmark": bench,
                "day_targeting": {
                    "target_days": target_days,
                    "well_selling_days": len(calendar) - len(target_days),
                },
                "events": [
                    {
                        "name": e.name,
                        "nights": f"{e.start.isoformat()}→{e.end.isoformat()}",
                        "impact": e.impact,
                    }
                    for e in events
                    if e.start < end and e.end > start
                ],
                "last_year_alignment": {"shift_days": shift.days, "aligned_on": aligned_on},
                "same_window_last_year": {
                    "occupancy": round(last_year.occupancy, 4),
                    "adr": round(last_year.adr, 2),
                },
            }
        }

    def route(state: ReviewState) -> str:
        if not state["analysis"]["pace_benchmark"]["behind"]:
            return "summarize"
        if state["analysis"]["rate_floor_reached"]:
            # Weak pace but nothing left to discount: proposing another cut
            # would be bad revenue management, so the LLM is never asked.
            return "summarize"
        return "propose"

    def _vs_benchmark(bench: dict) -> str:
        now = f"{bench['on_the_books_share']:.0%} of capacity on the books"
        if bench["basis"] == "fixed_threshold":
            return f"{now} (threshold {HEALTHY_OTB_SHARE:.0%}; no last-year history)"
        return (
            f"{now} vs {bench['last_year_share_same_lead_time']:.0%} "
            "at the same lead time last year"
        )

    def summarize(state: ReviewState) -> dict:
        bench = state["analysis"]["pace_benchmark"]
        window = f"{state['property_id']} {state['start']}→{state['end']}"
        if not bench["behind"]:
            return {"outcome": f"No action for {window}: {_vs_benchmark(bench)}."}
        limits = state["analysis"]["rate_limits"]
        avg = state["analysis"]["published_rates"]["avg"]
        return {
            "outcome": (
                f"No further discount for {window}: the average rate ${avg:.0f} is already at "
                f"the property's minimum rate ${limits['min']:.0f}. Price cuts are exhausted — "
                "consider non-price levers (minimum-stay rules, visibility, packages) or "
                "revisit the floor itself."
            )
        }

    def propose(state: ReviewState) -> dict:
        prompt = PROPOSE_PROMPT.format(
            max_pct=MAX_ADJUSTMENT_PCT, analysis=json.dumps(state["analysis"], indent=1)
        )
        return {"proposal": proposer.invoke(prompt).model_dump()}

    def enforce_constraints(state: ReviewState) -> dict:
        proposal = dict(state["proposal"])
        clamped = max(-MAX_ADJUSTMENT_PCT, min(MAX_ADJUSTMENT_PCT, proposal["adjustment_pct"]))
        if clamped != proposal["adjustment_pct"]:
            proposal["adjustment_pct"] = clamped
            proposal["rationale"] += f" [adjustment clamped to ±{MAX_ADJUSTMENT_PCT:.0f}% by policy]"
        return {"proposal": proposal}

    def human_approval(state: ReviewState) -> dict:
        current = state["analysis"]["pace"]["pace"][0]
        decision = interrupt(
            {
                "proposal": state["proposal"],
                "window": state["analysis"]["window"],
                "target_days": state["analysis"]["day_targeting"]["target_days"],
                "on_the_books": (
                    f"{current['nights_on_the_books']} nights — "
                    f"{_vs_benchmark(state['analysis']['pace_benchmark'])}"
                ),
            }
        )
        return {"decision": decision}

    def record(state: ReviewState) -> dict:
        """Publication happens HERE and only here: strictly after the human
        approval, through the separate write port — and only when a publisher
        was wired in at build time."""
        proposal, decision = state["proposal"], state["decision"]
        window = f"{state['property_id']} {state['start']}→{state['end']}"
        note = f" Note: {decision['note']}." if decision.get("note") else ""
        if not decision.get("approved"):
            return {"outcome": f"REJECTED: proposal for {window} was declined.{note}"}

        pct = proposal["adjustment_pct"]
        if publisher is None:
            return {
                "outcome": (
                    f"APPROVED: {pct:+.1f}% on published rates for {window}.{note} "
                    "(Recorded only — rate publication is not enabled.)"
                )
            }

        prop = pms.get_property(state["property_id"])
        factor = 1 + pct / 100
        targets = set(state["analysis"]["day_targeting"]["target_days"])
        current = pms.get_daily_rates(state["property_id"], state["start"], state["end"])
        new_rates = []
        bounded = 0
        for r in current:
            if r.day.isoformat() not in targets:
                continue  # selling at/above threshold: price stays
            raw = float(round(r.rate * factor))
            clamped = max(raw, prop.min_rate)
            if prop.max_rate is not None:
                clamped = min(clamped, prop.max_rate)
            if clamped != raw:
                bounded += 1
            new_rates.append(r.model_copy(update={"rate": clamped}))
        if not new_rates:
            return {
                "outcome": (
                    f"APPROVED, nothing to publish: every date in {window} is already "
                    f"pacing at or ahead of its benchmark.{note}"
                )
            }
        receipt = publisher.publish_rates(state["property_id"], new_rates)
        kept = len(current) - receipt.days
        kept_note = (
            f" — {kept} well-selling dates kept their price" if kept else ""
        )
        limits_note = (
            f" ({bounded} of {receipt.days} bounded by the rate limits "
            f"${prop.min_rate:.0f}–${prop.max_rate:.0f})"
            if bounded
            else ""
        )
        return {
            "outcome": (
                f"APPROVED & PUBLISHED: {pct:+.1f}% applied to {receipt.days} of "
                f"{len(current)} nightly rates for {window}{kept_note}{limits_note}.{note}"
            )
        }

    graph = StateGraph(ReviewState)
    graph.add_node("analyze", analyze)
    graph.add_node("summarize", summarize)
    graph.add_node("propose", propose)
    graph.add_node("enforce_constraints", enforce_constraints)
    graph.add_node("human_approval", human_approval)
    graph.add_node("record", record)

    graph.add_edge(START, "analyze")
    graph.add_conditional_edges("analyze", route)
    graph.add_edge("summarize", END)
    graph.add_edge("propose", "enforce_constraints")
    graph.add_edge("enforce_constraints", "human_approval")
    graph.add_edge("human_approval", "record")
    graph.add_edge("record", END)
    return graph.compile(checkpointer=checkpointer)
