"""Deterministic revenue analytics — the "calculator" layer.

Agents call these as tools and must never produce these numbers themselves.
The functions are pure (no I/O, no LLM), which makes them trivially testable.

Conventions:
- Date ranges are half-open: [start, end).
- Revenue for stays that straddle a range boundary is pro-rated per night.
- Only CONFIRMED reservations count toward realized performance; for
  "as of a moment in time" views, use on_the_books_nights, which reasons
  from booked_at / cancelled_at timestamps instead of final status.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from revenue_analyst.domain import Property, Reservation, ReservationStatus


class PerformanceSummary(BaseModel):
    property_id: str
    currency: str
    start: date
    end: date
    nights_available: int
    nights_sold: int
    occupancy: float
    revenue: float
    adr: float
    """Average daily rate: revenue / nights sold."""
    revpar: float
    """Revenue per available night: revenue / nights available."""


def _overlap_nights(reservation: Reservation, start: date, end: date) -> int:
    first = max(reservation.check_in, start)
    last = min(reservation.check_out, end)
    return max(0, (last - first).days)


def performance_summary(
    prop: Property, reservations: list[Reservation], start: date, end: date
) -> PerformanceSummary:
    days = (end - start).days
    if days <= 0:
        raise ValueError("end must be after start")

    nights_available = prop.unit_count * days
    nights_sold = 0
    revenue = 0.0
    for r in reservations:
        if r.status is not ReservationStatus.CONFIRMED:
            continue
        overlap = _overlap_nights(r, start, end)
        nights_sold += overlap
        revenue += r.total_amount * overlap / r.nights

    return PerformanceSummary(
        property_id=prop.id,
        currency=prop.currency,
        start=start,
        end=end,
        nights_available=nights_available,
        nights_sold=nights_sold,
        occupancy=nights_sold / nights_available,
        revenue=revenue,
        adr=revenue / nights_sold if nights_sold else 0.0,
        revpar=revenue / nights_available,
    )


def on_the_books_nights(
    reservations: list[Reservation], as_of: datetime, start: date, end: date
) -> int:
    """Nights sold in [start, end) as known at the moment `as_of`.

    A reservation counts if it had been booked by `as_of` and had not yet been
    cancelled at `as_of`. This is the building block of booking-pace analysis:
    compare on-the-books at different as-of moments to see pickup.
    """
    total = 0
    for r in reservations:
        if r.booked_at > as_of:
            continue
        if r.cancelled_at is not None and r.cancelled_at <= as_of:
            continue
        total += _overlap_nights(r, start, end)
    return total
