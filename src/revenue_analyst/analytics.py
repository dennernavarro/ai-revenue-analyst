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

from datetime import date, datetime, timedelta

from pydantic import BaseModel

from revenue_analyst.domain import DailyRate, Property, Reservation, ReservationStatus


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


class PacePoint(BaseModel):
    as_of: date
    nights_on_the_books: int
    share_of_capacity: float


class BookingPace(BaseModel):
    property_id: str
    start: date
    end: date
    capacity_nights: int
    pace: list[PacePoint]


def booking_pace(
    prop: Property,
    reservations: list[Reservation],
    as_of: datetime,
    start: date,
    end: date,
    lookback_days: tuple[int, ...] = (0, 30, 60, 90),
) -> BookingPace:
    """On-the-books nights for [start, end) at several past as-of moments.

    Comparing the points shows pickup: how fast the window has been filling.
    """
    if end <= start:
        raise ValueError("end must be after start")
    capacity = prop.unit_count * (end - start).days

    points = []
    for days_ago in lookback_days:
        moment = as_of - timedelta(days=days_ago)
        nights = on_the_books_nights(reservations, moment, start, end)
        points.append(
            PacePoint(
                as_of=moment.date(),
                nights_on_the_books=nights,
                share_of_capacity=round(nights / capacity, 4),
            )
        )
    return BookingPace(
        property_id=prop.id, start=start, end=end, capacity_nights=capacity, pace=points
    )


class CalendarDay(BaseModel):
    day: date
    rate: float
    min_stay: int
    nights_sold: int
    capacity: int


def daily_calendar(
    prop: Property,
    reservations: list[Reservation],
    rates: list[DailyRate],
    start: date,
    end: date,
) -> list[CalendarDay]:
    """Per-day occupancy and published rate for [start, end) — the data
    behind a hotel calendar view."""
    sold: dict[date, int] = {}
    for r in reservations:
        if r.status is not ReservationStatus.CONFIRMED:
            continue
        night = max(r.check_in, start)
        while night < min(r.check_out, end):
            sold[night] = sold.get(night, 0) + 1
            night += timedelta(days=1)

    rate_by_day = {r.day: r for r in rates}
    days = []
    day = start
    while day < end:
        rate = rate_by_day.get(day)
        days.append(
            CalendarDay(
                day=day,
                rate=rate.rate if rate else 0.0,
                min_stay=rate.min_stay if rate else 1,
                nights_sold=sold.get(day, 0),
                capacity=prop.unit_count,
            )
        )
        day += timedelta(days=1)
    return days


class RoomTypeOccupancy(BaseModel):
    room_type_id: str
    name: str
    units: int
    from_rate: float
    """Lowest published rate in the window × the category's multiplier."""
    nights_sold: int
    nights_available: int
    occupancy: float


def room_type_occupancy(
    prop: Property,
    reservations: list[Reservation],
    rates: list[DailyRate],
    start: date,
    end: date,
) -> list[RoomTypeOccupancy]:
    days = (end - start).days
    if days <= 0:
        raise ValueError("end must be after start")
    min_rate = min((r.rate for r in rates), default=0.0)
    unit_to_type = {u.id: u.room_type_id for u in prop.units}

    sold: dict[str, int] = {}
    for r in reservations:
        if r.status is not ReservationStatus.CONFIRMED:
            continue
        type_id = unit_to_type.get(r.unit_id)
        if type_id is not None:
            sold[type_id] = sold.get(type_id, 0) + _overlap_nights(r, start, end)

    result = []
    for room_type in prop.room_types:
        units = sum(1 for u in prop.units if u.room_type_id == room_type.id)
        available = units * days
        nights = sold.get(room_type.id, 0)
        result.append(
            RoomTypeOccupancy(
                room_type_id=room_type.id,
                name=room_type.name,
                units=units,
                from_rate=round(min_rate * room_type.rate_multiplier, 2),
                nights_sold=nights,
                nights_available=available,
                occupancy=nights / available if available else 0.0,
            )
        )
    return result


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


class SeasonMonth(BaseModel):
    month: int
    """1..12."""
    occupancy: float
    index: float
    """This month's occupancy / the year's average monthly occupancy."""
    level: str
    """"peak" (index ≥ 1.25), "high" (≥ 1.0), "shoulder" (≥ 0.8) or "low"."""


def season_profile(prop: Property, reservations: list[Reservation], year: int) -> list[SeasonMonth]:
    """How busy each month of `year` was, relative to that year's average —
    derived from realized bookings, so it works for any PMS (no config)."""
    occ = []
    for m in range(1, 13):
        start = date(year, m, 1)
        end = date(year + m // 12, m % 12 + 1, 1)
        occ.append(performance_summary(prop, reservations, start, end).occupancy)
    avg = sum(occ) / 12
    months = []
    for m, o in enumerate(occ, start=1):
        index = o / avg if avg else 0.0
        level = (
            "peak" if index >= 1.25 else "high" if index >= 1.0
            else "shoulder" if index >= 0.8 else "low"
        )
        months.append(SeasonMonth(month=m, occupancy=round(o, 4), index=round(index, 2), level=level))
    return months
