"""The PMS provider contract — the replaceable seam of this project.

Agents and analytics depend only on this Protocol. `MockPMS` implements it
from JSON files today; integrating a real PMS later means writing one new
adapter class that passes the same contract tests
(tests/test_pms_contract.py). Nothing above this seam changes.

Methods are synchronous on purpose: this is a learning project and sync code
is easier to read, test and trace. Making the seam async is a later exercise.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from revenue_analyst.domain import DailyRate, Property, RatePublication, Reservation


class PropertyNotFoundError(KeyError):
    """Raised when a provider does not know the requested property id."""


@runtime_checkable
class RatePublisher(Protocol):
    """The WRITE port — deliberately separate from PMSProvider.

    Reading PMS data must never imply permission to change prices: a
    component gets this capability only when it is wired in explicitly
    (see Settings.rate_publication), and the only caller is the pricing
    review's record step, which runs strictly after human approval.
    """

    def publish_rates(self, property_id: str, rates: list[DailyRate]) -> RatePublication:
        """Replace the published nightly rates for the given days."""
        ...


@runtime_checkable
class PMSProvider(Protocol):
    def list_properties(self) -> list[Property]: ...

    def get_property(self, property_id: str) -> Property:
        """Return one property. Raises PropertyNotFoundError for unknown ids."""
        ...

    def get_reservations(self, property_id: str, start: date, end: date) -> list[Reservation]:
        """All reservations (any status) whose stay overlaps [start, end)."""
        ...

    def get_daily_rates(self, property_id: str, start: date, end: date) -> list[DailyRate]:
        """Published nightly rates, one per day, for days in [start, end)."""
        ...
