"""Holiday and event calendar (Phase 2): date rules, no data.

Each rule maps a year to the nights [start, end) of that year's edition.
Moving holidays are computed (Easter, "third Monday of January"), so any year
works. A property's calendar is a selection of rules plus its own impact per
rule — the same Thanksgiving fills a ski cabin and empties a business hotel.

US public holidays follow the official rules. Local event dates are
illustrative approximations for the mock markets (Aspen, Chicago), not a
schedule to rely on.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

from revenue_analyst.domain import Event

MON, THU, FRI, SAT, SUN = 0, 3, 4, 5, 6


def easter(year: int) -> date:
    """Western Easter Sunday (anonymous Gregorian algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    lv = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * lv) // 451
    month, day = divmod(h + lv - 7 * m + 114, 31)
    return date(year, month, day + 1)


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The n-th `weekday` of a month; n = -1 is the last one."""
    if n > 0:
        first = date(year, month, 1)
        return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))
    nxt = date(year + month // 12, month % 12 + 1, 1)
    last = nxt - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _span(start: date, nights: int) -> tuple[date, date]:
    return start, start + timedelta(days=nights)


def _long_weekend(monday: date) -> tuple[date, date]:
    """Friday, Saturday and Sunday nights before a Monday holiday."""
    return _span(monday - timedelta(days=3), 3)


Rule = Callable[[int], tuple[date, date]]

RULES: dict[str, tuple[str, Rule]] = {
    # --- US public holidays -------------------------------------------------
    "MLK Day weekend": ("holiday", lambda y: _long_weekend(nth_weekday(y, 1, MON, 3))),
    "Presidents' Day weekend": ("holiday", lambda y: _long_weekend(nth_weekday(y, 2, MON, 3))),
    "Spring break": ("holiday", lambda y: _span(nth_weekday(y, 3, SAT, 2), 16)),
    "Easter weekend": ("holiday", lambda y: _span(easter(y) - timedelta(days=3), 4)),
    "Memorial Day weekend": ("holiday", lambda y: _long_weekend(nth_weekday(y, 5, MON, -1))),
    "Independence Day": ("holiday", lambda y: (date(y, 7, 3), date(y, 7, 6))),
    "Labor Day weekend": ("holiday", lambda y: _long_weekend(nth_weekday(y, 9, MON, 1))),
    "Thanksgiving": ("holiday", lambda y: _span(nth_weekday(y, 11, THU, 4) - timedelta(days=1), 4)),
    "Christmas & New Year": ("holiday", lambda y: (date(y, 12, 23), date(y + 1, 1, 2))),
    # --- local events (illustrative dates) ----------------------------------
    "X Games": ("event", lambda y: _span(nth_weekday(y, 1, THU, -1), 4)),
    "Food & Wine Classic": ("event", lambda y: _span(nth_weekday(y, 6, FRI, 3), 3)),
    "Lollapalooza": ("event", lambda y: _span(nth_weekday(y, 8, THU, 1), 4)),
    "Chicago Marathon": ("event", lambda y: _span(nth_weekday(y, 10, SUN, 2) - timedelta(days=2), 2)),
}


def calendar(property_id: str, impacts: dict[str, float], start: date, end: date) -> list[Event]:
    """Every edition of the property's events with a night in [start, end),
    sorted by start date. `impacts` maps rule names (keys of RULES) to the
    property's demand multiplier for that event."""
    events = []
    for name, impact in impacts.items():
        kind, rule = RULES[name]
        for year in range(start.year - 1, end.year + 1):
            ev_start, ev_end = rule(year)
            if ev_start < end and ev_end > start:
                events.append(
                    Event(
                        property_id=property_id, name=name, kind=kind,
                        start=ev_start, end=ev_end, impact=impact,
                    )
                )
    return sorted(events, key=lambda e: (e.start, e.name))


def impact_by_night(events: list[Event]) -> dict[date, float]:
    """Combined demand multiplier per night (overlapping events multiply)."""
    result: dict[date, float] = {}
    for e in events:
        night = e.start
        while night < e.end:
            result[night] = result.get(night, 1.0) * e.impact
            night += timedelta(days=1)
    return result


if __name__ == "__main__":
    # Self-check against known dates.
    assert easter(2025) == date(2025, 4, 20) and easter(2026) == date(2026, 4, 5)
    assert easter(2027) == date(2027, 3, 28)
    assert nth_weekday(2026, 11, THU, 4) == date(2026, 11, 26)  # Thanksgiving
    assert nth_weekday(2026, 5, MON, -1) == date(2026, 5, 25)  # Memorial Day
    assert nth_weekday(2026, 1, MON, 3) == date(2026, 1, 19)  # MLK Day
    assert nth_weekday(2026, 9, MON, 1) == date(2026, 9, 7)  # Labor Day
    print("ok")
