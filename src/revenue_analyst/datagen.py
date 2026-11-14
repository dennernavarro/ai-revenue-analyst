"""Deterministic mock-data generator.

Rather than inventing occupancy percentages, this simulates *booking
arrivals*: for each possible check-in day, a few booking requests arrive
(seasonal and day-of-week dependent), each with a length of stay, a lead time
and a channel. A request only becomes a reservation if a unit is free for the
whole stay — demand that finds no unit is lost. Occupancy, ADR, booking pace
and calendar gaps all emerge from this single process, so the data stays
internally consistent.

Bookings whose booking timestamp falls after AS_OF don't exist yet. That is
what makes future months look "partially booked" — exactly what a revenue
analyst reasons about.

Every property uses its own seeded RNG, so the output is fully reproducible.
"""

from __future__ import annotations

import math
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

from pydantic import BaseModel

from revenue_analyst.dataset import PropertyDataset
from revenue_analyst.domain import (
    DailyRate,
    Property,
    Reservation,
    ReservationStatus,
    RoomType,
    Unit,
)

HORIZON_START = date(2025, 1, 1)
HORIZON_END = date(2027, 3, 31)
AS_OF = datetime(2026, 11, 1, 12, 0)


class RoomTypeProfile(BaseModel):
    name: str
    count: int
    rate_multiplier: float = 1.0


class PropertyProfile(BaseModel):
    slug: str
    name: str
    city: str
    currency: str = "USD"
    seed: int
    room_types: list[RoomTypeProfile]
    base_rate: float
    month_factors: list[float]
    """Demand and rate multiplier per calendar month (Jan..Dec)."""
    dow_factors: list[float]
    """Demand multiplier per check-in weekday (Mon..Sun)."""
    weekend_rate_uplift: float
    """Rate multiplier applied on Friday and Saturday nights."""
    weekend_min_stay: int = 1
    daily_demand: float
    """Average booking requests per check-in day at multiplier 1.0."""
    mean_los: float
    mean_lead_days: float
    cancel_rate: float
    channels: dict[str, float]


PROFILES = [
    PropertyProfile(
        slug="seaside-villa",
        name="Seaside Villa",
        city="Santa Monica",
        seed=101,
        room_types=[RoomTypeProfile(name="Villa", count=1)],
        base_rate=320,
        month_factors=[0.55, 0.6, 0.7, 0.8, 1.0, 1.3, 1.5, 1.5, 1.2, 0.9, 0.6, 0.7],
        dow_factors=[0.8, 0.8, 0.8, 0.9, 1.3, 1.4, 1.0],
        weekend_rate_uplift=1.25,
        weekend_min_stay=2,
        daily_demand=0.35,
        mean_los=4.0,
        mean_lead_days=45,
        cancel_rate=0.12,
        channels={"airbnb": 0.5, "vrbo": 0.25, "direct": 0.25},
    ),
    PropertyProfile(
        slug="urban-boutique",
        name="Urban Boutique",
        city="Chicago",
        seed=202,
        room_types=[
            RoomTypeProfile(name="Standard Queen", count=6, rate_multiplier=0.95),
            RoomTypeProfile(name="Deluxe King", count=4, rate_multiplier=1.12),
            RoomTypeProfile(name="Corner Suite", count=2, rate_multiplier=1.4),
        ],
        base_rate=180,
        month_factors=[0.9, 0.9, 1.0, 1.05, 1.1, 1.1, 1.0, 0.95, 1.15, 1.2, 1.0, 0.85],
        dow_factors=[1.2, 1.3, 1.3, 1.2, 0.9, 0.7, 0.8],
        weekend_rate_uplift=0.9,
        daily_demand=4.0,
        mean_los=1.8,
        mean_lead_days=14,
        cancel_rate=0.18,
        channels={"booking.com": 0.45, "expedia": 0.2, "direct": 0.35},
    ),
    PropertyProfile(
        slug="mountain-cabins",
        name="Mountain Cabins",
        city="Aspen",
        seed=303,
        room_types=[RoomTypeProfile(name="Cabin", count=4)],
        base_rate=240,
        month_factors=[1.5, 1.4, 1.1, 0.7, 0.6, 0.8, 1.0, 1.0, 0.8, 0.7, 0.9, 1.4],
        dow_factors=[0.8, 0.7, 0.7, 0.9, 1.4, 1.5, 1.0],
        weekend_rate_uplift=1.3,
        weekend_min_stay=2,
        daily_demand=1.1,
        mean_los=3.0,
        mean_lead_days=30,
        cancel_rate=0.10,
        channels={"airbnb": 0.4, "direct": 0.4, "vrbo": 0.2},
    ),
]


def _poisson(rng: random.Random, lam: float) -> int:
    """Knuth's algorithm — fine for the small lambdas used here."""
    threshold = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        p *= rng.random()
        if p <= threshold:
            return k
        k += 1


def _each_day(start: date, end: date):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def _build_rates(profile: PropertyProfile, property_id: str) -> list[DailyRate]:
    rates = []
    for day in _each_day(HORIZON_START, HORIZON_END):
        factor = profile.month_factors[day.month - 1]
        is_weekend = day.weekday() in (4, 5)  # Friday and Saturday nights
        uplift = profile.weekend_rate_uplift if is_weekend else 1.0
        rates.append(
            DailyRate(
                property_id=property_id,
                day=day,
                rate=round(profile.base_rate * factor * uplift),
                min_stay=profile.weekend_min_stay if is_weekend else 1,
            )
        )
    return rates


def generate_dataset(profile: PropertyProfile) -> PropertyDataset:
    rng = random.Random(profile.seed)

    room_types = []
    units = []
    for rt_profile in profile.room_types:
        rt_id = f"{profile.slug}-{rt_profile.name.lower().replace(' ', '-')}"
        room_types.append(
            RoomType(id=rt_id, name=rt_profile.name, rate_multiplier=rt_profile.rate_multiplier)
        )
        single = rt_profile.count == 1 and len(profile.room_types) == 1
        for i in range(rt_profile.count):
            units.append(
                Unit(
                    id=f"{rt_id}-u{i + 1}",
                    name=rt_profile.name if single else f"{rt_profile.name} {i + 1}",
                    room_type_id=rt_id,
                )
            )
    prop = Property(
        id=profile.slug, name=profile.name, city=profile.city,
        currency=profile.currency, room_types=room_types, units=units,
        min_rate=round(profile.base_rate * 0.6),
        max_rate=round(profile.base_rate * 1.8),
    )

    daily_rates = _build_rates(profile, prop.id)
    rate_by_day = {r.day: r.rate for r in daily_rates}

    occupied: dict[str, set[date]] = {u.id: set() for u in units}
    reservations: list[Reservation] = []
    counter = 0

    for check_in in _each_day(HORIZON_START, HORIZON_END):
        demand = (
            profile.daily_demand
            * profile.month_factors[check_in.month - 1]
            * profile.dow_factors[check_in.weekday()]
        )
        for _ in range(_poisson(rng, demand)):
            # Draw everything up front so the RNG sequence stays stable even
            # when a request is discarded below.
            los = min(21, 1 + int(rng.expovariate(1.0 / max(profile.mean_los - 1.0, 0.1))))
            lead = min(365, int(rng.expovariate(1.0 / profile.mean_lead_days)))
            booked_time = time(rng.randint(6, 23), rng.randint(0, 59))
            channel = rng.choices(list(profile.channels), weights=list(profile.channels.values()))
            cancel_roll = rng.random()
            cancel_frac = rng.random()

            booked_at = datetime.combine(check_in, booked_time) - timedelta(days=lead)
            if booked_at > AS_OF:
                continue  # this booking hasn't happened yet
            check_out = check_in + timedelta(days=los)
            if check_out > HORIZON_END:
                continue

            stay = [check_in + timedelta(days=i) for i in range(los)]
            unit_id = next((u.id for u in units if occupied[u.id].isdisjoint(stay)), None)
            if unit_id is None:
                continue  # sold out: this demand is lost

            status = ReservationStatus.CONFIRMED
            cancelled_at = None
            if cancel_roll < profile.cancel_rate:
                check_in_noon = datetime.combine(check_in, time(12))
                when = max(booked_at, booked_at + (check_in_noon - booked_at) * cancel_frac)
                if when <= AS_OF:
                    status = ReservationStatus.CANCELLED
                    cancelled_at = when
            if status is ReservationStatus.CONFIRMED:
                occupied[unit_id].update(stay)

            counter += 1
            multiplier = prop.room_type_of(unit_id).rate_multiplier
            reservations.append(
                Reservation(
                    id=f"{profile.slug}-r{counter:05d}",
                    property_id=prop.id,
                    unit_id=unit_id,
                    check_in=check_in,
                    check_out=check_out,
                    booked_at=booked_at,
                    status=status,
                    channel=channel[0],
                    total_amount=round(sum(rate_by_day[d] for d in stay) * multiplier, 2),
                    cancelled_at=cancelled_at,
                )
            )

    reservations.sort(key=lambda r: (r.check_in, r.id))
    return PropertyDataset(
        as_of=AS_OF, property=prop, reservations=reservations, daily_rates=daily_rates
    )


def write_datasets(data_dir: str | Path) -> list[Path]:
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for profile in PROFILES:
        dataset = generate_dataset(profile)
        path = data_dir / f"{profile.slug}.json"
        path.write_text(dataset.model_dump_json())
        paths.append(path)
    return paths
