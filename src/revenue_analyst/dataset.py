"""On-disk dataset format shared by the data generator and the mock PMS."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from revenue_analyst.domain import DailyRate, Property, Reservation


class PropertyDataset(BaseModel):
    as_of: datetime
    """The simulated "today": no booking in the dataset was made after this."""

    property: Property
    reservations: list[Reservation]
    daily_rates: list[DailyRate]
