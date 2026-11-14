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

# December 2026 at Mountain Cabins paces ~21% as of Nov 1 → below threshold.
WEAK_WINDOW = {"property_id": "mountain-cabins", "start": date(2026, 12, 1), "end": date(2027, 1, 1)}
# November 2026 paces ~45% → healthy.
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


def test_weak_pace_pauses_then_records_approval(scripted_model):
    proposal = RateProposal(
        adjustment_pct=-12,
        rationale="Only 21% on the books vs 40% threshold.",
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


def test_approval_publishes_rates_through_the_write_port(scripted_model):
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

    workflow.invoke(WEAK_WINDOW, CONFIG)
    resumed = workflow.invoke(Command(resume={"approved": True, "note": ""}), CONFIG)

    assert resumed["outcome"].startswith("APPROVED & PUBLISHED: -10.0%")
    after = {r.day: r.rate for r in pms.get_daily_rates("mountain-cabins", *window)}
    assert all(after[day] == float(round(rate * 0.9)) for day, rate in before.items())


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


def test_out_of_bounds_proposal_is_clamped_by_policy(scripted_model):
    # The "LLM" proposes -60%; policy caps at ±25% regardless.
    proposal = RateProposal(adjustment_pct=-60, rationale="panic", expected_effect="volume")
    workflow = _workflow(scripted_model, structured=[proposal])
    result = workflow.invoke(WEAK_WINDOW, CONFIG)
    clamped = result["__interrupt__"][0].value["proposal"]
    assert clamped["adjustment_pct"] == -25.0
    assert "clamped" in clamped["rationale"]
