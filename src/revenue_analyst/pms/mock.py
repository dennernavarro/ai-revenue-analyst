"""Mock PMS adapter: a PMSProvider implementation backed by JSON files."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from revenue_analyst.dataset import PropertyDataset
from revenue_analyst.domain import DailyRate, Property, Reservation
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
        return [dr for dr in self._dataset(property_id).daily_rates if start <= dr.day < end]

    # --- mock-only extras (not part of the Protocol) --------------------------

    def as_of(self, property_id: str) -> datetime:
        """The simulated "today" of this property's dataset."""
        return self._dataset(property_id).as_of
