# Plan

Roadmap to make the analyst season- and holiday-aware. Phases run in order;
each one ends with tests green, STATUS.md updated and a release.

Measurement comes first (Phase 1): every later phase changes pricing
behaviour, and we need a way to tell whether a change helps before it ships.

---

## Phase 0 — Foundation ✅ code done, commit pending

**Goal:** a season-aware baseline and shared project docs.

- [x] Pricing review: benchmark against last year's on-the-books at the same
      lead time (364-day shift, 90% tolerance); fixed 40% only without history.
- [x] Tests: seasonal case (below 40% but ahead of LY → no action) and the
      no-history fallback.
- [x] Docs: BRAND, CODE_STANDARDS, PROCESS, SPEC, STATUS, TECH_STACK, PLAN.
- [ ] Commit on a branch, PR, merge, release 1.2.0.

---

## Phase 1 — Measurement: backtesting and seasonal evals

**Goal:** score any pricing rule on history before it reaches users.

- Backtest harness (`backtest.py` + `scripts/`): replay the review at past
  `as_of` dates over the seeded history; report per window what it would have
  done (no action / discount / days targeted) and what actually happened
  (final occupancy, revenue vs last year).
- Scoring: did "behind" windows actually end below LY? Did "no action"
  windows end at/above LY? (precision / recall of the routing rule.)
- Evals (`evals.py`): add seasonal questions — "how does December compare to
  last December?", "is January pacing behind?" — with ground truth computed
  from `analytics.py`.
- Extend simulated history to ≥ 2 full years before "today" so multi-year
  comparisons are possible (`datagen.HORIZON_START`).

**Done when:** one command prints a backtest report for all properties, and
the Phase 0 rule has a recorded baseline score in STATUS.md.

---

## Phase 2 — Holiday and event calendar

**Goal:** holidays and local events are first-class, and last-year
comparisons align by event, not by date.

- Data: `data/events/<property>.json` — `{name, start, end, kind:
  holiday|event, impact}`; public holidays per market (Easter, Carnival,
  Thanksgiving, Christmas/New Year, local school breaks) plus local events
  (ski-season opening, marathons, conferences).
- Port: `PMSProvider` (or a separate `EventsProvider`) exposes events for a
  range; mock reads the JSON.
- Simulator realism (`datagen.py`): event demand/rate multipliers, longer lead
  times for holidays, season-dependent lead time and cancellation rate — so
  the mock data actually contains what we want to detect.
- Event-aligned benchmark: when a window contains a moving holiday, compare
  with the same holiday last year (e.g. Easter 2027 ↔ Easter 2026) instead of
  the plain 364-day shift.
- Chat: `get_events` tool so the agent can explain "Christmas week is strong
  because…"; dashboard calendar marks event days.

**Done when:** Easter/Carnival windows benchmark against the right dates, the
chat names events in answers, and the backtest score does not regress.

---

## Phase 3 — Pace curves vs last year, everywhere

**Goal:** the user sees seasonality, not just the review.

- `booking_pace` returns last year's OTB at the same lead times next to the
  0/30/60/90-day points (and pickup between them).
- `GET /properties/{id}/pace` and the `get_booking_pace` tool include the
  last-year series; `get_performance` can return the same period last year.
- Dashboard: pace chart (this year vs last year) and "vs LY" deltas on the
  KPI tiles.
- Prompts: answer "how are we doing?" relative to last year by default.

**Done when:** "How is January pacing?" is answered with a vs-last-year
comparison from tool data, and the dashboard shows the pace curve.

---

## Phase 4 — Price increases on strong dates

**Goal:** capture peak demand, not just fill low demand.

- New route: window (or days) **ahead** of benchmark by a margin → propose an
  increase, applied only to dates filled above benchmark and not yet sold out.
- Separate policy constants for increases (e.g. +15% cap per review) and the
  existing `max_rate` ceiling.
- Approval card shows direction clearly ("raise" vs "discount").
- Backtest both directions.

**Done when:** a peak/holiday window pacing ahead gets an increase proposal,
bounded and approved like discounts, with backtest evidence.

---

## Phase 5 — Seasonal rules: floors, ceilings and minimum stays

**Goal:** policies that change with the season and events.

- Seasonal `min_rate` / `max_rate` (per month or per season/event) instead of
  one value all year.
- Min-stay rules per season/event (e.g. 7 nights over Christmas, 2 nights on
  weekends in peak), and gap-night handling (allow short stays that fill
  1–2-night holes).
- Review can propose min-stay changes as a non-price lever (today it only
  mentions them in text).

**Done when:** rates and min-stays respect seasonal policies, and the review
can propose a min-stay change through the same approval flow.

---

## Phase 6 — Forecast-based decisions

**Goal:** decide on expected final occupancy, not just "behind last year".

- Pickup forecast: expected final = OTB now + expected remaining pickup from
  this lead time (from history, by season and event).
- Seasonal occupancy/revenue targets per property; route on forecast vs
  target. Handles growth (new units, new listings) that "vs last year" gets
  wrong.
- Multi-year averages to smooth noise; per-day benchmarks once history is
  rich enough (replaces the `ponytail:` single-window benchmark).

**Done when:** the review routes on the forecast, and the backtest shows it
beats the Phase 0 rule.

---

## Phase 7 — Real data

**Goal:** run on a real PMS and market signal.

- PMS adapter from `pms/template.py` with at least 12–24 months of history
  (required for the benchmark; otherwise the fixed-threshold fallback).
- External market/demand signal (e.g. a market-data provider such as
  PriceLabs neighbourhood data) as an optional input to the benchmark and
  forecast.
- Persistent rate publication and review store (replace in-memory mocks).

**Done when:** a real property runs end-to-end with history-based benchmarks
and approvals publish to the real PMS.

---

## Out of scope

Automatic repricing without approval; multi-tenant auth; taxes/fees.
