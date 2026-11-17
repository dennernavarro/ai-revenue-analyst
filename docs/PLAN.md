# Plan

Roadmap to make the analyst season- and holiday-aware. Phases run in order;
each one ends with tests green, STATUS.md updated and a release.

Measurement comes first (Phase 1): every later phase changes pricing
behaviour, and we need a way to tell whether a change helps before it ships.

---

## Phase 0 — Foundation ✅ done (PR #2 open)

**Goal:** a season-aware baseline and shared project docs.

- [x] Pricing review: benchmark against last year's on-the-books at the same
      lead time (364-day shift, 90% tolerance); fixed 40% only without history.
- [x] Tests: seasonal case (below 40% but ahead of LY → no action) and the
      no-history fallback.
- [x] Docs: BRAND, CODE_STANDARDS, PROCESS, SPEC, STATUS, TECH_STACK, PLAN.
- [x] Commit on a branch and open a PR (#2).
- [ ] Merge, release 1.2.0.

---

## Phase 1 — Measurement: backtesting and seasonal evals 🚧 in progress

**Goal:** score any pricing rule on history before it reaches users.

- [x] Backtest harness (`python -m revenue_analyst.backtest`): replays the
      routing rule at 30/60/90 days before each finished month, scores it
      against the do-nothing outcome, next to the fixed 40% rule. The rule
      is one pure function (`pace_benchmark`) shared by the review and the
      backtest.
- [x] Scoring: precision / recall / accuracy of "behind" flags, per lead time.
- [x] Baseline recorded in STATUS.md.
- [ ] Night-level scoring: replay a per-night rule next to the per-window
      one and score both on history (were the flagged nights the ones that
      ended below last year?). Gate for Phase 4: if night-level doesn't beat
      window-level, Auto-pilot stays window-level.
- [ ] Evals (`evals.py`): add seasonal questions — "how does December compare
      to last December?", "is January pacing behind?" — with ground truth
      computed from `analytics.py`.
- [ ] Extend simulated history to ≥ 2 full years before "today" so
      multi-year comparisons are possible and the backtest has more windows
      (`datagen.HORIZON_START`; today only Jan–Oct 2026 are testable).
- [ ] Low-signal guard, informed by the baseline: when last year had too few
      nights on the books at this lead time, report "too early to judge"
      instead of flagging (most false flags are 0–4% vs 0–4%).

**Done when:** one command prints a backtest report for all properties, and
the Phase 0 rule has a recorded baseline score in STATUS.md.

---

## Phase 2 — Holiday and event calendar 🚧 in progress

**Goal:** holidays and local events are first-class, and last-year
comparisons align by event, not by date.

- [x] Date rules (`events.py`): US holidays incl. Easter, plus illustrative
      local events (X Games, Food & Wine, Lollapalooza, Chicago Marathon);
      impact per property (Thanksgiving ×1.3 at the cabins, ×0.5 at the city
      hotel).
- [x] Port: `PMSProvider.get_events`; mock stores events in the dataset,
      the template returns `[]` (plain 364-day comparison).
- [x] Simulator: event demand and rate multipliers, longer lead times for
      peaks. Not yet: season-dependent cancellation rate.
- [x] Event-aligned benchmark: shift to the previous edition of the window's
      main event in whole weeks (Easter 2027 ↔ Easter 2026 = 357 days);
      backtest gains an `event_aligned` rule.
- [ ] Chat: `get_events` tool so the agent can explain "Christmas week is
      strong because…"; `GET /properties/{id}/events`.
- [ ] Calendar UI per the approved Claude Design canvas ("Revenue Calendar
      Redesign"): clean cells (date, price, fill shade, event line, behind
      dot), every detail in the day card, chat as a side panel, purple look.
      BRAND.md updated to match.
- [ ] Simulator bugs found on the way: event uplift publishes rates above
      `max_rate` (Mountain Cabins Christmas $655 > $432), and low-season
      rates fall below `min_rate` (Seaside Villa January $176 < $192).

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

## Phase 4 — Auto-pilot: night-level reviews, queued for approval

**Goal:** the deep agent reviews upcoming dates every day and lines up price
(and minimum-stay) changes; nothing publishes without a person's OK.

Why night-level: a month can be ahead while some of its nights are not.
Prototype on the mock data (Nov 2026): Seaside Villa's December is ahead
(52% vs 35%), yet all five Christmas nights are empty while similar nights
last year were ~90% booked by now — a per-month check never sees it.

- [ ] **Per-night benchmark**: each night vs last year's nights *of the same
      type* (weekday / weekend / event night) within ±7 days, at the same
      lead time, aligned by event. Pooling gives enough signal even for a
      1-unit villa.
- [ ] **Low-signal guard**: when those peers had < 25% booked by now, the
      night is "too early to tell" (Watching), not a suggestion.
- [ ] **Urgency**: nights closer to arrival need less evidence; far-out
      nights need more.
- [ ] **Group** flagged nights (gaps ≤ 1 night) into one suggestion each.
- [ ] **Per-night prices**: the change applies night by night, clamped to
      min/max rate; later, separate % for weekdays / weekends / event nights.
- [ ] **Non-price fixes** (rule-based, no LLM): a night nobody can book —
      e.g. a 2-night minimum next to a sold-out night (Mountain Cabins
      Dec 25) — gets "allow 1-night stays" instead of a discount.
- [ ] **Fact check**: every number and comparison in the agent's rationale
      must match the analysis, else it is regenerated or hidden (live runs
      produced "$275 is significantly above $290" and "0.0 booked last year"
      when it was high).
- [ ] **Cool-down**: no new suggestion for nights changed in the last 7 days.
- [ ] **Queue**: persistent store for suggestions + audit log; Approve
      publishes via `RatePublisher`, Not now snoozes a day, suggestions
      withdraw themselves when bookings catch up or the dates pass.
- [ ] **Scheduler**: daily run (default 07:00, next 120 days, all properties).
- [ ] UI per the design: header switch, banner, Auto-pilot page grouped by
      urgency, day card shows the night's suggestion.

**Done when:** a daily run produces grouped, fact-checked suggestions that
beat the window-level rule in the night-level backtest, and approving one
publishes only its nights.

**Open decision:** approval stays mandatory (current design). Letting
Auto-pilot publish small changes on its own would change a core invariant
(SPEC.md) and needs an explicit decision.

---

## Phase 5 — Price increases on strong dates

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

## Phase 6 — Seasonal rules: floors, ceilings and minimum stays

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

## Phase 7 — Forecast-based decisions

**Goal:** decide on expected final occupancy, not just "behind last year".

- Pickup forecast: expected final = OTB now + expected remaining pickup from
  this lead time (from history, by season and event).
- Seasonal occupancy/revenue targets per property; route on forecast vs
  target. Handles growth (new units, new listings) that "vs last year" gets
  wrong.
- Multi-year averages to smooth noise; replaces the pooled per-night
  benchmark of Phase 4 once history is rich enough.

**Done when:** the review routes on the forecast, and the backtest shows it
beats the Phase 0 rule.

---

## Phase 8 — Real data

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
