"""Starting point for a real PMS integration.

Copy this file to pms/<vendor>.py, fill in the TODOs, register the class in
pms/factory.py, and add it to the contract-test fixture
(tests/test_pms_contract.py). When the contract suite passes, the
integration is complete — nothing above the provider seam changes.

Ground rules that make the integration painless:

- **Normalize at the edge.** Vendor payloads become the canonical models
  from domain.py inside this class; nothing vendor-shaped may leak out.
- **check_out is exclusive** everywhere in this codebase: a Fri→Sun stay
  occupies Fri and Sat nights. Convert if your vendor uses inclusive dates.
- **booked_at is the reservation's CREATION timestamp** (and cancelled_at
  the cancellation moment). All booking-pace analytics are reconstructed
  from these two fields — verify your vendor exposes them before anything
  else. If it truly does not, pace features degrade to "current value only".
- **Rates are for the reference room category** (RoomType.rate_multiplier
  1.0); other categories price as rate × multiplier. If your vendor prices
  per category per day, pick a reference category here and derive the
  multipliers.
- **Auth, pagination, retries and caching live HERE.** The dashboard calls
  these methods on every page load, so cache reads with a short TTL (even
  60s) instead of hitting the vendor API per request.
- Raise PropertyNotFoundError for unknown ids; the tools turn it into a
  recoverable error the agent can act on.
"""

from __future__ import annotations

from datetime import date

from revenue_analyst.domain import DailyRate, Property, RatePublication, Reservation
from revenue_analyst.pms.provider import PropertyNotFoundError  # noqa: F401  (raise it below)


class TemplatePMSAdapter:
    """Skeleton PMSProvider. Every method raises until you fill it in."""

    def __init__(self) -> None:
        # TODO: credentials and endpoint come from env vars or Settings
        # (add fields there), e.g.:
        #   self._base_url = os.environ["MYPMS_BASE_URL"]
        #   self._api_key = os.environ["MYPMS_API_KEY"]
        # TODO: create your HTTP client here (httpx.Client with timeout and
        # retries) and a small read cache: dict[(method, args) -> (expires,
        # value)].
        pass

    # --- PMSProvider (read) ---------------------------------------------------

    def list_properties(self) -> list[Property]:
        # TODO: GET /properties → map each payload to Property:
        #   - room_types: vendor room categories (id, name, rate multiplier
        #     relative to the reference category)
        #   - units: physical rooms/listings, each with room_type_id
        #   - min_rate / max_rate: the business floor and ceiling; if the
        #     vendor has no concept for them, put them in your own config —
        #     the pricing guardrails depend on these being real.
        raise NotImplementedError("TemplatePMSAdapter.list_properties: fill in the TODO")

    def get_property(self, property_id: str) -> Property:
        # TODO: single fetch, or filter list_properties(); raise
        # PropertyNotFoundError(property_id) for unknown ids.
        raise NotImplementedError("TemplatePMSAdapter.get_property: fill in the TODO")

    def get_reservations(self, property_id: str, start: date, end: date) -> list[Reservation]:
        # TODO: every reservation whose stay OVERLAPS [start, end) — any
        # status, cancellations included. Handle vendor pagination here.
        # Field mapping checklist:
        #   check_in / check_out (exclusive!), unit_id, status
        #   booked_at   <- reservation creation timestamp (critical)
        #   cancelled_at<- cancellation timestamp, None if active
        #   channel, total_amount (whole stay, property currency)
        raise NotImplementedError("TemplatePMSAdapter.get_reservations: fill in the TODO")

    def get_daily_rates(self, property_id: str, start: date, end: date) -> list[DailyRate]:
        # TODO: one DailyRate per day in [start, end) for the REFERENCE
        # category: day, nightly rate, min_stay restriction.
        raise NotImplementedError("TemplatePMSAdapter.get_daily_rates: fill in the TODO")

    # --- RatePublisher (write) — optional -------------------------------------

    def publish_rates(self, property_id: str, rates: list[DailyRate]) -> RatePublication:
        # OPTIONAL: only needed if approved pricing reviews should publish.
        # Without it, set RA_RATE_PUBLICATION=false (record-only mode).
        # TODO: push the new nightly rates to the vendor; make it IDEMPOTENT
        # (same payload twice = same result) and return a RatePublication
        # receipt. Remember: the workflow already clamped the values into
        # [min_rate, max_rate] — do not re-derive prices here.
        raise NotImplementedError("TemplatePMSAdapter.publish_rates: fill in the TODO")
