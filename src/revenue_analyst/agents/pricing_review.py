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
- The routing decision (healthy vs weak pace) is a threshold in Python, not a
  judgment call delegated to the LLM.
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

from revenue_analyst.analytics import booking_pace, daily_calendar, performance_summary
from revenue_analyst.llm import init_model
from revenue_analyst.pms.provider import PMSProvider, RatePublisher

HEALTHY_OTB_SHARE = 0.40
"""On-the-books share of capacity above which no action is proposed.
Deliberately naive — a real RMS compares against historical pace curves."""

MAX_ADJUSTMENT_PCT = 25.0
"""Business policy: no single adjustment beyond ±25%, enforced in code."""


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
You are a revenue analyst. A future stay window is pacing below target.
Based ONLY on the analysis below (JSON), propose ONE rate adjustment within
±{max_pct}% and justify it with those numbers. "same_window_last_year" uses a
364-day shift so weekdays align.

Respect "rate_limits": published rates can never leave that band, so if
current rates are already close to the floor, propose only the small cut that
still fits (or focus the rationale on non-price levers) — repeated deep
discounts on already-discounted rates destroy revenue.

Your adjustment will be applied ONLY to the dates in
"day_targeting.target_days" (those pacing below the threshold); dates already
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

        pace = booking_pace(prop, pms.get_reservations(prop.id, start, end), as_of, start, end)
        rates = pms.get_daily_rates(prop.id, start, end)
        ly_start, ly_end = start - timedelta(days=364), end - timedelta(days=364)
        last_year = performance_summary(
            prop, pms.get_reservations(prop.id, ly_start, ly_end), ly_start, ly_end
        )

        avg_rate = round(mean(r.rate for r in rates), 2) if rates else 0.0
        # Discounts are exhausted once the average sits at (or within 2% of)
        # the property's hard floor — a deterministic fact, not a judgment.
        floor_reached = bool(rates) and avg_rate <= prop.min_rate * 1.02

        # Day-level targeting: an adjustment only makes sense on dates that
        # are pacing BELOW the threshold. Dates already selling well — or
        # sold out — keep their price; discounting them burns revenue.
        window_reservations = pms.get_reservations(prop.id, start, end)
        calendar = daily_calendar(prop, window_reservations, rates, start, end)
        target_days = [
            day.day.isoformat()
            for day in calendar
            if day.capacity and day.nights_sold / day.capacity < HEALTHY_OTB_SHARE
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
                "day_targeting": {
                    "threshold": HEALTHY_OTB_SHARE,
                    "target_days": target_days,
                    "well_selling_days": len(calendar) - len(target_days),
                },
                "same_window_last_year": {
                    "occupancy": round(last_year.occupancy, 4),
                    "adr": round(last_year.adr, 2),
                },
            }
        }

    def route(state: ReviewState) -> str:
        current_share = state["analysis"]["pace"]["pace"][0]["share_of_capacity"]
        if current_share >= HEALTHY_OTB_SHARE:
            return "summarize"
        if state["analysis"]["rate_floor_reached"]:
            # Weak pace but nothing left to discount: proposing another cut
            # would be bad revenue management, so the LLM is never asked.
            return "summarize"
        return "propose"

    def summarize(state: ReviewState) -> dict:
        current = state["analysis"]["pace"]["pace"][0]
        window = f"{state['property_id']} {state['start']}→{state['end']}"
        if current["share_of_capacity"] >= HEALTHY_OTB_SHARE:
            return {
                "outcome": (
                    f"No action for {window}: {current['share_of_capacity']:.0%} of capacity "
                    f"already on the books (threshold {HEALTHY_OTB_SHARE:.0%})."
                )
            }
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
                    f"{current['nights_on_the_books']} nights "
                    f"({current['share_of_capacity']:.0%} of capacity)"
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
                    f"selling at or above {HEALTHY_OTB_SHARE:.0%}.{note}"
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
