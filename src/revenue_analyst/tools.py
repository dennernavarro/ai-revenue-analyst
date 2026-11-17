"""LangChain tools over the deterministic analytics layer (Stage 1).

Two lessons live in this file:

1. **The docstring is the interface.** The LLM never sees your code — it sees
   each tool's name, docstring and argument schema, and decides what to call
   from those alone. Writing a tool docstring IS prompt engineering: say what
   the tool answers, what the arguments mean, and what comes back.

2. **Dependency injection without magic.** `build_tools` closes over a
   `PMSProvider` and a clock (`as_of`), so the tools work identically over the
   mock PMS today or a real one later, and tests can inject whatever they want.

All tools are read-only and return plain dicts (JSON-friendly), with numbers
computed by analytics.py — never by the model.
"""

from __future__ import annotations

from datetime import date, datetime

from langchain_core.tools import BaseTool, tool

from revenue_analyst.analytics import booking_pace, performance_summary
from revenue_analyst.pms.provider import PMSProvider, PropertyNotFoundError


def _unknown_property(pms: PMSProvider, property_id: str) -> dict:
    """A graceful tool error: tell the model what went wrong AND how to recover."""
    return {
        "error": f"Unknown property_id {property_id!r}.",
        "valid_property_ids": [p.id for p in pms.list_properties()],
    }


def build_tools(pms: PMSProvider, as_of: datetime) -> list[BaseTool]:
    """Build the analyst's toolbox over any PMSProvider.

    `as_of` is the moment "now" for booking-pace questions — injected instead
    of read from the wall clock so simulated data and tests stay deterministic.
    """

    @tool
    def list_properties() -> list[dict]:
        """List all managed properties with their id, name, city and unit count.

        Call this first to discover the valid property_id values used by every
        other tool.
        """
        return [
            {"property_id": p.id, "name": p.name, "city": p.city, "units": p.unit_count}
            for p in pms.list_properties()
        ]

    @tool
    def get_performance(property_id: str, start_date: date, end_date: date) -> dict:
        """Realized performance of one property over a past date range.

        Dates are ISO format (YYYY-MM-DD) and the range is half-open:
        end_date is NOT included, so a full month ends on the 1st of the NEXT
        month (full August = 2026-08-01 to 2026-09-01, never ...-08-31).

        Returns nights available/sold, occupancy (0..1), total revenue, ADR
        (average daily rate = revenue / nights sold) and RevPAR (revenue per
        available night), in the property's currency.
        """
        try:
            prop = pms.get_property(property_id)
        except PropertyNotFoundError:
            return _unknown_property(pms, property_id)
        reservations = pms.get_reservations(property_id, start_date, end_date)
        summary = performance_summary(prop, reservations, start_date, end_date)
        data = summary.model_dump(mode="json")
        data["occupancy"] = round(summary.occupancy, 4)
        for key in ("revenue", "adr", "revpar"):
            data[key] = round(data[key], 2)
        return data

    @tool
    def get_booking_pace(property_id: str, start_date: date, end_date: date) -> dict:
        """Booking pace for a (usually future) stay window: how many nights are
        already sold ("on the books") today and how many were sold 30/60/90
        days ago. Also THE source for capacity questions — the result includes
        capacity_nights (units × nights); never compute capacity yourself.

        Dates are ISO format (YYYY-MM-DD); the range is half-open (end_date
        excluded), so a full month ends on the 1st of the NEXT month:
        December 2026 is 2026-12-01 to 2027-01-01, never ...-12-31.
        Comparing the values shows pickup — how fast the window is filling.
        Nights on the books exclude reservations cancelled by each as-of
        moment.
        """
        try:
            prop = pms.get_property(property_id)
        except PropertyNotFoundError:
            return _unknown_property(pms, property_id)
        reservations = pms.get_reservations(property_id, start_date, end_date)
        result = booking_pace(prop, reservations, as_of, start_date, end_date)
        return result.model_dump(mode="json")

    @tool
    def get_rates(property_id: str, start_date: date, end_date: date) -> dict:
        """Published nightly rates of one property for a date range.

        Dates are ISO format (YYYY-MM-DD); the range is half-open (end_date
        excluded) and is capped at 62 days per call. Returns min/avg/max plus
        the per-day rate and minimum-stay restriction.
        """
        try:
            pms.get_property(property_id)
        except PropertyNotFoundError:
            return _unknown_property(pms, property_id)
        if (end_date - start_date).days > 62:
            return {"error": "Date range too long: request at most 62 days per call."}
        rates = pms.get_daily_rates(property_id, start_date, end_date)
        if not rates:
            return {"error": f"No published rates between {start_date} and {end_date}."}
        values = [r.rate for r in rates]
        return {
            "property_id": property_id,
            "min_rate": min(values),
            "avg_rate": round(sum(values) / len(values), 2),
            "max_rate": max(values),
            "days": [
                {"day": r.day.isoformat(), "rate": r.rate, "min_stay": r.min_stay}
                for r in rates
            ],
        }

    @tool
    def get_events(property_id: str, start_date: date, end_date: date) -> dict:
        """Holidays and local events affecting one property in a date range.

        Dates are ISO format (YYYY-MM-DD), half-open (end_date excluded). Each
        event has its nights [start, end), a kind ("holiday" or "event") and
        an impact: this property's typical demand multiplier (1.0 neutral,
        2.0 = demand usually doubles, 0.5 = usually halves). Use it to explain
        why dates are strong or weak.
        """
        try:
            pms.get_property(property_id)
        except PropertyNotFoundError:
            return _unknown_property(pms, property_id)
        events = pms.get_events(property_id, start_date, end_date)
        return {
            "property_id": property_id,
            "events": [
                {
                    "name": e.name, "kind": e.kind, "start": e.start.isoformat(),
                    "end": e.end.isoformat(), "impact": e.impact,
                }
                for e in events
            ],
        }

    return [list_properties, get_performance, get_booking_pace, get_rates, get_events]
