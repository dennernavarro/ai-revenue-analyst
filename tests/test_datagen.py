from collections import Counter

from revenue_analyst.datagen import AS_OF, PROFILES, generate_dataset
from revenue_analyst.domain import ReservationStatus


def test_generation_is_deterministic():
    profile = PROFILES[0]
    first = generate_dataset(profile)
    second = generate_dataset(profile)
    assert first.model_dump() == second.model_dump()


def test_no_booking_exists_after_as_of():
    dataset = generate_dataset(PROFILES[0])
    assert all(r.booked_at <= AS_OF for r in dataset.reservations)


def test_no_confirmed_double_bookings():
    dataset = generate_dataset(PROFILES[1])  # the multi-unit hotel
    nights_per_unit: dict[str, Counter] = {}
    for r in dataset.reservations:
        if r.status is not ReservationStatus.CONFIRMED:
            continue
        counter = nights_per_unit.setdefault(r.unit_id, Counter())
        for offset in range(r.nights):
            counter[r.check_in.toordinal() + offset] += 1
    for unit_id, counter in nights_per_unit.items():
        overbooked = [night for night, n in counter.items() if n > 1]
        assert not overbooked, f"unit {unit_id} double-booked on {len(overbooked)} nights"
