"""The eval harness itself is deterministic code, so it gets unit tests:
scoring logic, number extraction, the half-open-window check, and the
guarantee that dataset ground truth matches the analytics layer."""

from datetime import date
from pathlib import Path

from revenue_analyst.analytics import performance_summary
from revenue_analyst.datagen import AS_OF
from revenue_analyst.evals import (
    Example,
    build_dataset,
    extract_numbers,
    full_month_windows_ok,
    has_number,
    score,
)
from revenue_analyst.pms.mock import MockPMS

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def test_number_extraction_and_tolerance():
    reply = "Occupancy was 77.42% with an ADR of $510.00 and revenue of $12,240."
    assert extract_numbers(reply) == [77.42, 510.0, 12240.0]
    assert has_number(reply, 77.419, tol=0.15)
    assert has_number(reply, 12240, tol=0.5)
    assert not has_number(reply, 394.84, tol=0.5)


def test_full_month_window_check_catches_the_classic_bug():
    good = [{"name": "get_booking_pace", "args": {"start_date": "2026-12-01", "end_date": "2027-01-01"}}]
    bad = [{"name": "get_booking_pace", "args": {"start_date": "2026-12-01", "end_date": "2026-12-31"}}]
    partial = [{"name": "get_rates", "args": {"start_date": "2026-12-10", "end_date": "2026-12-20"}}]
    assert full_month_windows_ok(good)
    assert not full_month_windows_ok(bad)
    assert full_month_windows_ok(partial), "mid-month windows are not full-month claims"


def test_score_combines_checks():
    example = Example(
        question="q",
        expected_tools={"get_performance"},
        numbers=[(510.0, 0.5)],
        text_all=["Seaside Villa"],
    )
    checks = score(
        example,
        reply="Seaside Villa had an ADR of $510.",
        tool_calls=[{"name": "get_performance", "args": {}}],
    )
    assert checks == {"tools": True, "numbers": True, "text": True}

    checks = score(example, reply="ADR was about $500.", tool_calls=[])
    assert checks["tools"] is False and checks["numbers"] is False


def test_dataset_ground_truth_matches_analytics():
    pms = MockPMS(DATA_DIR)
    dataset = build_dataset(pms, AS_OF)
    assert len(dataset) >= 9

    prop = pms.get_property("seaside-villa")
    aug = (date(2026, 8, 1), date(2026, 9, 1))
    summary = performance_summary(prop, pms.get_reservations(prop.id, *aug), *aug)
    villa = next(e for e in dataset if "Seaside Villa in August" in e.question)
    assert villa.numbers[0][0] == summary.occupancy * 100
    assert villa.numbers[1][0] == summary.adr
