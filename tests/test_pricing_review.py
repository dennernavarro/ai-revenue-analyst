"""The pricing-review workflow runs offline: the one LLM slot is stubbed with
a fixed RateProposal, everything else is deterministic."""

from datetime import date
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from revenue_analyst.agents.pricing_review import RateProposal, build_pricing_review
from revenue_analyst.datagen import AS_OF
from revenue_analyst.pms.mock import MockPMS

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CONFIG = {"configurable": {"thread_id": "review-test"}}

# January 2027 at Mountain Cabins: 3% on the books vs 8% at the same lead
# time last year → behind.
WEAK_WINDOW = {"property_id": "mountain-cabins", "start": date(2027, 1, 1), "end": date(2027, 2, 1)}
# December 2026: only 20% on the books — below the old fixed 40% — but ahead
# of last year's 17% at the same lead time → no action.
SEASONAL_WINDOW = {
    "property_id": "mountain-cabins",
    "start": date(2026, 12, 1),
    "end": date(2027, 1, 1),
}
# November 2026: 44% vs 38% last year → healthy.
HEALTHY_WINDOW = {
    "property_id": "mountain-cabins",
    "start": date(2026, 11, 1),
    "end": date(2026, 12, 1),
}


def _workflow(scripted_model, structured=()):
    return build_pricing_review(
        MockPMS(DATA_DIR),
        AS_OF,
        model=scripted_model(structured=structured),
        checkpointer=InMemorySaver(),
    )


def test_healthy_pace_short_circuits_without_the_llm(scripted_model):
    # No structured outputs are scripted: if the LLM slot were reached, the
    # stub would raise StopIteration. Routing must bypass it.
    workflow = _workflow(scripted_model)
    result = workflow.invoke(HEALTHY_WINDOW, CONFIG)
    assert "No action" in result["outcome"]
    assert "__interrupt__" not in result


def test_pace_is_judged_against_last_year_not_a_fixed_threshold(scripted_model):
    # Below 40% yet ahead of last year: the LLM must not be reached.
    result = _workflow(scripted_model).invoke(SEASONAL_WINDOW, CONFIG)
    assert "__interrupt__" not in result
    assert "No action" in result["outcome"]
    assert "same lead time last year" in result["outcome"]


def test_without_history_falls_back_to_the_fixed_threshold(scripted_model):
    class NoHistoryPMS(MockPMS):
        def get_reservations(self, property_id, start, end):
            if end <= AS_OF.date():
                return []
            return super().get_reservations(property_id, start, end)

    proposal = RateProposal(adjustment_pct=-5, rationale="slow", expected_effect="pickup")
    workflow = build_pricing_review(
        NoHistoryPMS(DATA_DIR),
        AS_OF,
        model=scripted_model(structured=[proposal]),
        checkpointer=InMemorySaver(),
    )
    # Same December window: with no history, 20% < 40% → proposal.
    payload = workflow.invoke(SEASONAL_WINDOW, CONFIG)["__interrupt__"][0].value
    assert "no last-year history" in payload["on_the_books"]


def test_weak_pace_pauses_then_records_approval(scripted_model):
    proposal = RateProposal(
        adjustment_pct=-12,
        rationale="3% on the books vs 8% last year.",
        expected_effect="Higher pickup at slightly lower ADR.",
    )
    workflow = _workflow(scripted_model, structured=[proposal])

    result = workflow.invoke(WEAK_WINDOW, CONFIG)
    payload = result["__interrupt__"][0].value
    assert payload["proposal"]["adjustment_pct"] == -12

    resumed = workflow.invoke(Command(resume={"approved": True, "note": "ok"}), CONFIG)
    assert resumed["outcome"].startswith("APPROVED: -12.0%")
    assert "Note: ok" in resumed["outcome"]


def test_rejection_is_recorded(scripted_model):
    proposal = RateProposal(adjustment_pct=-12, rationale="slow", expected_effect="pickup")
    workflow = _workflow(scripted_model, structured=[proposal])
    workflow.invoke(WEAK_WINDOW, CONFIG)
    resumed = workflow.invoke(Command(resume={"approved": False, "note": ""}), CONFIG)
    assert resumed["outcome"].startswith("REJECTED")


def test_approval_publishes_only_to_slow_pacing_days(scripted_model):
    pms = MockPMS(DATA_DIR)
    proposal = RateProposal(adjustment_pct=-10, rationale="slow", expected_effect="pickup")
    workflow = build_pricing_review(
        pms,
        AS_OF,
        model=scripted_model(structured=[proposal]),
        checkpointer=InMemorySaver(),
        publisher=pms,
    )
    window = (WEAK_WINDOW["start"], WEAK_WINDOW["end"])
    before = {r.day: r.rate for r in pms.get_daily_rates("mountain-cabins", *window)}

    paused = workflow.invoke(WEAK_WINDOW, CONFIG)
    targets = {date.fromisoformat(d) for d in paused["__interrupt__"][0].value["target_days"]}
    # Jan 16–19 already have a cabin sold (25%), above the ~7% benchmark.
    assert date(2027, 1, 17) not in targets and date(2027, 1, 5) in targets
    expected = {
        day: float(round(rate * 0.9)) if day in targets else rate for day, rate in before.items()
    }
    resumed = workflow.invoke(Command(resume={"approved": True, "note": ""}), CONFIG)

    assert resumed["outcome"].startswith("APPROVED & PUBLISHED: -10.0%")
    after = {r.day: r.rate for r in pms.get_daily_rates("mountain-cabins", *window)}
    assert after == expected


def test_rejection_leaves_rates_untouched(scripted_model):
    pms = MockPMS(DATA_DIR)
    proposal = RateProposal(adjustment_pct=-10, rationale="slow", expected_effect="pickup")
    workflow = build_pricing_review(
        pms,
        AS_OF,
        model=scripted_model(structured=[proposal]),
        checkpointer=InMemorySaver(),
        publisher=pms,
    )
    window = (WEAK_WINDOW["start"], WEAK_WINDOW["end"])
    before = [r.rate for r in pms.get_daily_rates("mountain-cabins", *window)]
    workflow.invoke(WEAK_WINDOW, CONFIG)
    workflow.invoke(Command(resume={"approved": False, "note": ""}), CONFIG)
    assert [r.rate for r in pms.get_daily_rates("mountain-cabins", *window)] == before


def test_published_rates_never_go_below_the_property_floor(scripted_model):
    """Seaside Villa: floor $192 (base 320 × 0.6). A -25% cut would take the
    $224 weekdays to $168 — publication must stop at the floor, while the
    $280 weekends land at $210 above it. The sold-out nights (Dec 1–3, 1/1
    sold) must keep their $224: never discount a day that is selling."""
    pms = MockPMS(DATA_DIR)
    window = {"property_id": "seaside-villa", "start": date(2026, 12, 1), "end": date(2027, 1, 1)}
    proposal = RateProposal(adjustment_pct=-25, rationale="deep cut", expected_effect="volume")
    workflow = build_pricing_review(
        pms, AS_OF, model=scripted_model(structured=[proposal]),
        checkpointer=InMemorySaver(), publisher=pms,
    )
    paused = workflow.invoke(window, CONFIG)
    target_days = paused["__interrupt__"][0].value["target_days"]
    assert "2026-12-01" not in target_days  # sold out → not a target
    assert "2026-12-07" in target_days

    resumed = workflow.invoke(Command(resume={"approved": True, "note": ""}), CONFIG)

    assert "bounded by the rate limits" in resumed["outcome"]
    assert "well-selling dates kept their price" in resumed["outcome"]
    rates = {
        r.day.isoformat(): r.rate
        for r in pms.get_daily_rates("seaside-villa", window["start"], window["end"])
    }
    assert rates["2026-12-01"] == 224.0  # sold out: untouched
    assert rates["2026-12-07"] == 192.0  # slow weekday: floor, not 168
    assert rates["2026-12-04"] == 210.0  # slow weekend: 280 × 0.75


def test_exhausted_discounts_skip_the_llm_entirely(scripted_model):
    """Rates already at the floor + weak pace → deterministic 'no further
    discount' outcome; any LLM call would make the stub raise StopIteration."""
    pms = MockPMS(DATA_DIR)
    prop = pms.get_property("seaside-villa")
    start, end = date(2026, 12, 1), date(2027, 1, 1)
    floored = [
        r.model_copy(update={"rate": float(prop.min_rate)})
        for r in pms.get_daily_rates("seaside-villa", start, end)
    ]
    pms.publish_rates("seaside-villa", floored)

    workflow = build_pricing_review(
        pms, AS_OF, model=scripted_model(), checkpointer=InMemorySaver(), publisher=pms
    )
    result = workflow.invoke({"property_id": "seaside-villa", "start": start, "end": end}, CONFIG)
    assert "__interrupt__" not in result
    assert "No further discount" in result["outcome"]
    assert "non-price levers" in result["outcome"]


def test_out_of_bounds_proposal_is_clamped_by_policy(scripted_model):
    # The "LLM" proposes -60%; policy caps at ±25% regardless.
    proposal = RateProposal(adjustment_pct=-60, rationale="panic", expected_effect="volume")
    workflow = _workflow(scripted_model, structured=[proposal])
    result = workflow.invoke(WEAK_WINDOW, CONFIG)
    clamped = result["__interrupt__"][0].value["proposal"]
    assert clamped["adjustment_pct"] == -25.0
    assert "clamped" in clamped["rationale"]
