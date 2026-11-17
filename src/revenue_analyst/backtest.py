"""Phase 1: backtest the pricing review's routing rule on history.

    uv run python -m revenue_analyst.backtest            # summary
    uv run python -m revenue_analyst.backtest --verbose  # plus every decision

For every property, every finished month and several lead times, rebuild what
was on the books at that past moment (bookings carry booked_at/cancelled_at,
so this is exact), ask the rule "is this window behind?", then compare with
what actually happened.

The question the rule answers is "will this window end below last year if
we do nothing?". Nothing was ever repriced in this history, so the final
result IS the do-nothing outcome — a clean ground truth:

    actually behind = final occupancy < PACE_TOLERANCE × last year's final

Both rules are scored on the same windows: the last-year benchmark the
review uses, and the old fixed 40% threshold (the no-history fallback).
No LLM involved — only the deterministic routing decision is replayed.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta

from revenue_analyst.agents.pricing_review import (
    LAST_YEAR_SHIFT,
    PACE_TOLERANCE,
    pace_benchmark,
)
from revenue_analyst.analytics import performance_summary
from revenue_analyst.pms.provider import PMSProvider

LEAD_DAYS = (30, 60, 90)
RULES = ("last_year", "fixed_40")


def _months(first: date, last: date):
    """Full calendar months [start, end) from `first` up to `last` (exclusive)."""
    start = first.replace(day=1)
    while True:
        end = (start + timedelta(days=32)).replace(day=1)
        if end > last:
            return
        yield start, end
        start = end


def run_backtest(
    pms: PMSProvider, first: date, last: date, leads: tuple[int, ...] = LEAD_DAYS
) -> list[dict]:
    """One row per (property, month in [first, last), lead time).

    Callers must pick months that are finished (end ≤ the data's as_of) and
    whose last-year window lies inside the recorded history.
    """
    rows = []
    for prop in pms.list_properties():
        for start, end in _months(first, last):
            reservations = pms.get_reservations(prop.id, start, end)
            ly_start, ly_end = start - LAST_YEAR_SHIFT, end - LAST_YEAR_SHIFT
            ly_reservations = pms.get_reservations(prop.id, ly_start, ly_end)
            final = performance_summary(prop, reservations, start, end).occupancy
            ly_final = performance_summary(prop, ly_reservations, ly_start, ly_end).occupancy
            actual_behind = final < ly_final * PACE_TOLERANCE

            for lead in leads:
                decided_at = datetime.combine(start - timedelta(days=lead), time(12))
                bench = pace_benchmark(
                    prop, reservations, ly_reservations, decided_at, start, end
                )
                fixed = pace_benchmark(prop, reservations, [], decided_at, start, end)
                rows.append(
                    {
                        "property_id": prop.id,
                        "month": start.strftime("%Y-%m"),
                        "lead_days": lead,
                        "otb_share": bench["on_the_books_share"],
                        "ly_otb_share": bench["last_year_share_same_lead_time"],
                        "final_occupancy": round(final, 4),
                        "ly_final_occupancy": round(ly_final, 4),
                        "actual_behind": actual_behind,
                        "last_year": bench["behind"],
                        "fixed_40": fixed["behind"],
                    }
                )
    return rows


def score(rows: list[dict], rule: str) -> dict:
    """Confusion counts for one rule. "Positive" = flagged behind (would
    trigger a proposal). Precision: of the flags, how many were right.
    Recall: of the windows that really ended behind, how many were caught."""
    tp = sum(r[rule] and r["actual_behind"] for r in rows)
    fp = sum(r[rule] and not r["actual_behind"] for r in rows)
    fn = sum(not r[rule] and r["actual_behind"] for r in rows)
    tn = len(rows) - tp - fp - fn
    return {
        "n": len(rows),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "accuracy": (tp + tn) / len(rows) if rows else None,
    }


def _pct(x: float | None) -> str:
    return "  n/a" if x is None else f"{x:5.0%}"


def report(rows: list[dict], verbose: bool = False) -> str:
    lines = []
    if verbose:
        lines.append("property          month    lead  otb   LY-otb  final  LY-final  "
                     "actual   last_year  fixed_40")
        for r in rows:
            ly_otb = "  n/a" if r["ly_otb_share"] is None else f"{r['ly_otb_share']:5.0%}"
            lines.append(
                f"{r['property_id']:17} {r['month']}  {r['lead_days']:3}d "
                f"{r['otb_share']:5.0%} {ly_otb}  {r['final_occupancy']:5.0%}  "
                f"{r['ly_final_occupancy']:5.0%}     "
                f"{'behind' if r['actual_behind'] else 'ok':7}  "
                f"{'flag' if r['last_year'] else '-':9}  {'flag' if r['fixed_40'] else '-'}"
            )
        lines.append("")

    behind = sum(r["actual_behind"] for r in rows)
    lines.append(f"{len(rows)} decisions, {behind} windows actually ended behind last year")
    lines.append("")
    lines.append("rule        lead   flags  precision  recall  accuracy   (tp/fp/fn/tn)")
    for rule in RULES:
        for lead in (*sorted({r["lead_days"] for r in rows}), None):
            subset = [r for r in rows if lead is None or r["lead_days"] == lead]
            s = score(subset, rule)
            label = "all" if lead is None else f"{lead}d"
            lines.append(
                f"{rule:10}  {label:>4}  {s['tp'] + s['fp']:5}  {_pct(s['precision']):>9}  "
                f"{_pct(s['recall']):>6}  {_pct(s['accuracy']):>8}   "
                f"({s['tp']}/{s['fp']}/{s['fn']}/{s['tn']})"
            )
    return "\n".join(lines)


def main() -> None:
    from revenue_analyst.config import Settings
    from revenue_analyst.pms.factory import build_provider

    parser = argparse.ArgumentParser(description="Backtest the pricing-review routing rule")
    parser.add_argument("--first", type=date.fromisoformat, default=date(2026, 1, 1),
                        help="first month to replay (default 2026-01-01)")
    parser.add_argument("--last", type=date.fromisoformat, default=date(2026, 11, 1),
                        help="replay months ending on or before this date (default 2026-11-01)")
    parser.add_argument("--verbose", action="store_true", help="print every decision")
    args = parser.parse_args()

    rows = run_backtest(build_provider(Settings()), args.first, args.last)
    print(report(rows, verbose=args.verbose))


if __name__ == "__main__":
    main()
