"""Provider contract tests — the guarantee behind the replaceable PMS seam.

These tests express what ANY PMSProvider implementation must do. They run
against MockPMS today; when a real PMS adapter is added, parametrize the
`provider` fixture with it and the same suite verifies the integration.
"""

from datetime import date, timedelta
from pathlib import Path

import pytest

from revenue_analyst.pms.mock import MockPMS
from revenue_analyst.pms.provider import PMSProvider, PropertyNotFoundError

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
WINDOW = (date(2026, 6, 1), date(2026, 7, 1))


@pytest.fixture(params=["mock"])
def provider(request) -> PMSProvider:
    return MockPMS(DATA_DIR)


def test_lists_properties_with_units(provider):
    properties = provider.list_properties()
    assert len(properties) >= 1
    for prop in properties:
        assert prop.units, f"{prop.id} has no units"


def test_get_property_roundtrip(provider):
    for prop in provider.list_properties():
        assert provider.get_property(prop.id) == prop


def test_unknown_property_raises(provider):
    with pytest.raises(PropertyNotFoundError):
        provider.get_property("does-not-exist")


def test_reservations_overlap_the_window(provider):
    for prop in provider.list_properties():
        reservations = provider.get_reservations(prop.id, *WINDOW)
        assert reservations, f"{prop.id}: expected some reservations in {WINDOW}"
        for r in reservations:
            assert r.property_id == prop.id
            assert r.check_in < WINDOW[1] and r.check_out > WINDOW[0]


def test_narrow_window_is_subset_of_wide(provider):
    narrow = (WINDOW[0] + timedelta(days=7), WINDOW[1] - timedelta(days=7))
    for prop in provider.list_properties():
        wide_ids = {r.id for r in provider.get_reservations(prop.id, *WINDOW)}
        narrow_ids = {r.id for r in provider.get_reservations(prop.id, *narrow)}
        assert narrow_ids <= wide_ids


def test_rate_publication_applies_in_memory_only(provider):
    """The write port: published rates are visible through get_daily_rates,
    scoped to the published days, and never touch the seed files (a fresh
    provider instance still sees the original rates)."""
    window = (date(2026, 12, 1), date(2026, 12, 4))
    prop = provider.list_properties()[0]
    before = provider.get_daily_rates(prop.id, *window)
    original = [r.rate for r in before]
    outside_before = provider.get_daily_rates(prop.id, date(2026, 12, 4), date(2026, 12, 5))

    new_rates = [r.model_copy(update={"rate": r.rate + 11.0}) for r in before]
    receipt = provider.publish_rates(prop.id, new_rates)
    assert receipt.days == len(new_rates)

    after = provider.get_daily_rates(prop.id, *window)
    assert [r.rate for r in after] == [rate + 11.0 for rate in original]
    outside_after = provider.get_daily_rates(prop.id, date(2026, 12, 4), date(2026, 12, 5))
    assert outside_after[0].rate == outside_before[0].rate  # untouched day

    fresh = MockPMS(DATA_DIR)
    assert [r.rate for r in fresh.get_daily_rates(prop.id, *window)] == original


def test_rates_cover_every_day_exactly_once(provider):
    expected_days = [
        WINDOW[0] + timedelta(days=i) for i in range((WINDOW[1] - WINDOW[0]).days)
    ]
    for prop in provider.list_properties():
        rates = provider.get_daily_rates(prop.id, *WINDOW)
        assert sorted(r.day for r in rates) == expected_days
        assert all(r.rate > 0 for r in rates)
