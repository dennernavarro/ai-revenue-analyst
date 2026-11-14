"""The tools are exercised exactly as an LLM would call them: by name, with
JSON-ish arguments (dates as ISO strings), via .invoke()."""

from datetime import date
from pathlib import Path

import pytest

from revenue_analyst.analytics import performance_summary
from revenue_analyst.datagen import AS_OF
from revenue_analyst.pms.mock import MockPMS
from revenue_analyst.tools import build_tools

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def pms() -> MockPMS:
    return MockPMS(DATA_DIR)


@pytest.fixture(scope="module")
def tools(pms) -> dict:
    return {t.name: t for t in build_tools(pms, AS_OF)}


def test_every_tool_documents_itself(tools):
    for t in tools.values():
        assert t.description, f"{t.name} has no docstring"
        if t.name != "list_properties":
            assert set(t.args) == {"property_id", "start_date", "end_date"}


def test_list_properties(tools, pms):
    listed = tools["list_properties"].invoke({})
    assert {p["property_id"] for p in listed} == {p.id for p in pms.list_properties()}


def test_get_performance_matches_analytics(tools, pms):
    args = {"property_id": "seaside-villa", "start_date": "2026-08-01", "end_date": "2026-09-01"}
    result = tools["get_performance"].invoke(args)

    start, end = date(2026, 8, 1), date(2026, 9, 1)
    prop = pms.get_property("seaside-villa")
    expected = performance_summary(
        prop, pms.get_reservations(prop.id, start, end), start, end
    )
    assert result["nights_sold"] == expected.nights_sold
    assert result["occupancy"] == pytest.approx(expected.occupancy, abs=1e-4)
    assert result["revenue"] == pytest.approx(expected.revenue, abs=0.01)


def test_unknown_property_returns_recoverable_error(tools):
    result = tools["get_performance"].invoke(
        {"property_id": "nope", "start_date": "2026-08-01", "end_date": "2026-09-01"}
    )
    assert "error" in result
    assert "seaside-villa" in result["valid_property_ids"]


def test_booking_pace_shape(tools):
    result = tools["get_booking_pace"].invoke(
        {"property_id": "mountain-cabins", "start_date": "2026-12-01", "end_date": "2027-01-01"}
    )
    assert result["capacity_nights"] == 4 * 31
    assert result["pace"][0]["as_of"] == AS_OF.date().isoformat()
    assert all(0 <= p["nights_on_the_books"] <= result["capacity_nights"] for p in result["pace"])


def test_rates_summary_and_cap(tools):
    result = tools["get_rates"].invoke(
        {"property_id": "urban-boutique", "start_date": "2026-06-01", "end_date": "2026-07-01"}
    )
    assert result["min_rate"] <= result["avg_rate"] <= result["max_rate"]
    assert len(result["days"]) == 30

    too_long = tools["get_rates"].invoke(
        {"property_id": "urban-boutique", "start_date": "2026-01-01", "end_date": "2026-12-01"}
    )
    assert "error" in too_long
