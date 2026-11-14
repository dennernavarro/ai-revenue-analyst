"""Mock PMS adapter: a PMSProvider implementation backed by JSON files."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from revenue_analyst.dataset import PropertyDataset
from revenue_analyst.domain import DailyRate, Property, RatePublication, Reservation
from revenue_analyst.pms.provider import PropertyNotFoundError


class MockPMS:
    def __init__(self, data_dir: str | Path) -> None:
        self._datasets: dict[str, PropertyDataset] = {}
        for path in sorted(Path(data_dir).glob("*.json")):
            dataset = PropertyDataset.model_validate_json(path.read_text())
            self._datasets[dataset.property.id] = dataset
        if not self._datasets:
            raise FileNotFoundError(
                f"No property datasets found in {data_dir} — run scripts/generate_data.py"
            )

    def _dataset(self, property_id: str) -> PropertyDataset:
        try:
            return self._datasets[property_id]
        except KeyError:
            raise PropertyNotFoundError(property_id) from None

    # --- PMSProvider contract -------------------------------------------------

    def list_properties(self) -> list[Property]:
        return [dataset.property for dataset in self._datasets.values()]

    def get_property(self, property_id: str) -> Property:
        return self._dataset(property_id).property

    def get_reservations(self, property_id: str, start: date, end: date) -> list[Reservation]:
        return [
            r
            for r in self._dataset(property_id).reservations
            if r.check_in < end and r.check_out > start
        ]

    def get_daily_rates(self, property_id: str, start: date, end: date) -> list[DailyRate]:
        # Copies, not references: rates are mutable through publish_rates, and
        # leaking the stored objects would let reads alias later writes.
        return [
            dr.model_copy()
            for dr in self._dataset(property_id).daily_rates
            if start <= dr.day < end
        ]

    # --- RatePublisher contract (the separate WRITE port) ---------------------

    def publish_rates(self, property_id: str, rates: list[DailyRate]) -> RatePublication:
        """Apply new nightly rates IN MEMORY: the seed JSON on disk stays
        untouched (the simulator remains the reproducible ground truth), so a
        process restart returns to the generated rates."""
        if not rates:
            raise ValueError("publish_rates needs at least one rate")
        dataset = self._dataset(property_id)
        by_day = {r.day: r for r in dataset.daily_rates}
        for new in rates:
            existing = by_day.get(new.day)
            if existing is None:
                dataset.daily_rates.append(new)
            else:
                existing.rate = new.rate
                existing.min_stay = new.min_stay
        days = sorted(r.day for r in rates)
        return RatePublication(
            property_id=property_id,
            days=len(rates),
            start=days[0],
            end=days[-1] + timedelta(days=1),
            published_at=datetime.now(),
        )

    # --- mock-only extras (not part of the Protocol) --------------------------

    def as_of(self, property_id: str) -> datetime:
        """The simulated "today" of this property's dataset."""
        return self._dataset(property_id).as_of
