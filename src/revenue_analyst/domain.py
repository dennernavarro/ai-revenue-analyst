"""Canonical domain models.

Everything above the PMS seam — analytics, tools, agents, API — speaks these
models and nothing else. A real PMS adapter must translate its vendor payloads
into these before they cross the provider boundary (see pms/provider.py).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, model_validator


class Unit(BaseModel):
    """A bookable unit: a hotel room, a cabin, a villa."""

    id: str
    name: str


class Property(BaseModel):
    id: str
    name: str
    city: str
    currency: str = "USD"
    units: list[Unit]

    @property
    def unit_count(self) -> int:
        return len(self.units)


class ReservationStatus(str, Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class Reservation(BaseModel):
    """A guest stay.

    `check_out` is exclusive: a Fri→Sun stay occupies the Fri and Sat nights.
    `status` is the reservation's final state in the dataset; for "as of a
    given moment" questions (e.g. booking pace), use `booked_at` and
    `cancelled_at` instead — see analytics.on_the_books_nights.
    """

    id: str
    property_id: str
    unit_id: str
    check_in: date
    check_out: date
    booked_at: datetime
    status: ReservationStatus
    channel: str
    total_amount: float
    cancelled_at: datetime | None = None

    @model_validator(mode="after")
    def _validate(self) -> Reservation:
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        if self.status is ReservationStatus.CANCELLED and self.cancelled_at is None:
            raise ValueError("cancelled reservations must have cancelled_at")
        return self

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days


class DailyRate(BaseModel):
    """The published nightly rate for one property on one calendar day."""

    property_id: str
    day: date
    rate: float
    min_stay: int = 1
