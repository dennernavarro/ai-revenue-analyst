from datetime import date, datetime

import pytest

from revenue_analyst.analytics import on_the_books_nights, performance_summary
from revenue_analyst.domain import Property, Reservation, ReservationStatus, Unit

PROP = Property(
    id="p1",
    name="Test Inn",
    city="Testville",
    units=[Unit(id="u1", name="Room 1"), Unit(id="u2", name="Room 2")],
)


def _res(
    res_id: str,
    unit: str,
    check_in: date,
    nights: int,
    total: float,
    status: ReservationStatus = ReservationStatus.CONFIRMED,
    booked_at: datetime = datetime(2026, 1, 1, 10, 0),
    cancelled_at: datetime | None = None,
) -> Reservation:
    return Reservation(
        id=res_id,
        property_id=PROP.id,
        unit_id=unit,
        check_in=check_in,
        check_out=date.fromordinal(check_in.toordinal() + nights),
        booked_at=booked_at,
        status=status,
        channel="direct",
        total_amount=total,
        cancelled_at=cancelled_at,
    )


class TestPerformanceSummary:
    START, END = date(2026, 6, 1), date(2026, 6, 11)  # 10 days, 2 units = 20 unit-nights

    def summary(self, reservations):
        return performance_summary(PROP, reservations, self.START, self.END)

    def test_basic_kpis(self):
        reservations = [
            # fully inside the window: 5 nights, $500
            _res("a", "u1", date(2026, 6, 1), nights=5, total=500),
            # straddles the window start: 4 nights total, only 2 inside → $200 pro-rated
            _res("b", "u2", date(2026, 5, 30), nights=4, total=400),
            # cancelled: must not count
            _res(
                "c", "u2", date(2026, 6, 4), nights=2, total=999,
                status=ReservationStatus.CANCELLED, cancelled_at=datetime(2026, 5, 1),
            ),
        ]
        s = self.summary(reservations)
        assert s.nights_available == 20
        assert s.nights_sold == 7
        assert s.revenue == pytest.approx(700.0)
        assert s.occupancy == pytest.approx(7 / 20)
        assert s.adr == pytest.approx(100.0)
        assert s.revpar == pytest.approx(35.0)

    def test_empty(self):
        s = self.summary([])
        assert s.nights_sold == 0
        assert s.adr == 0.0
        assert s.revpar == 0.0

    def test_invalid_range(self):
        with pytest.raises(ValueError):
            performance_summary(PROP, [], self.END, self.START)


class TestOnTheBooks:
    START, END = date(2026, 12, 1), date(2027, 1, 1)

    def test_respects_booking_and_cancellation_timestamps(self):
        reservations = [
            # booked in October, stays booked: counts
            _res("a", "u1", date(2026, 12, 10), nights=5, total=1000,
                 booked_at=datetime(2026, 10, 1)),
            # booked after the as-of moment: does not exist yet
            _res("b", "u2", date(2026, 12, 12), nights=3, total=600,
                 booked_at=datetime(2026, 11, 20)),
            # booked in October but cancelled before as-of: gone
            _res("c", "u2", date(2026, 12, 20), nights=4, total=800,
                 status=ReservationStatus.CANCELLED,
                 booked_at=datetime(2026, 10, 1), cancelled_at=datetime(2026, 10, 20)),
        ]
        as_of_nov = datetime(2026, 11, 1)
        assert on_the_books_nights(reservations, as_of_nov, self.START, self.END) == 5

        # earlier in time, the later-cancelled booking was still on the books
        as_of_oct = datetime(2026, 10, 10)
        assert on_the_books_nights(reservations, as_of_oct, self.START, self.END) == 9
