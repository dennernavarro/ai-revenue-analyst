# Status

_Last updated: 2026-11-17_

**Version:** 1.1.0 (`main` @ `23c8770`) + unmerged work below.
**Phase:** 1 — measurement, in progress (see PLAN.md).

## Working

- Mock PMS with 3 properties (Seaside Villa, Urban Boutique, Mountain Cabins),
  seeded history 2025-01-01 → 2027-03-31, "today" 2026-11-01.
- Deterministic analytics, REST API, dashboard at `/ui`, chat agent, deep
  agent, pricing review with human approval and rate publication.
- Tests: 58 passed, 7 skipped (offline). Ruff clean. CI on GitHub Actions.
- Verified live with OpenRouter (`gpt-4o-mini`): chat answers match the KPI
  tiles; reviews behave as below.

## On branch `feat/season-aware-pricing-review` (not merged yet)

- **Pricing review benchmarks against last year's pace at the same lead
  time** (90% tolerance, 364-day shift), with fixed 40% only when there is no
  history. Live results:

  | Window | OTB now vs LY same lead | Outcome |
  |---|---|---|
  | Mountain Cabins Dec 2026 | 20% vs 17% | No action (was: discount) |
  | Mountain Cabins Jan 2027 | 3% vs 8% | −10% proposed on 27 days |
  | Seaside Villa Dec 2026 | 10% vs 29% | −10% proposed on 28 days |

- Project docs in `docs/`: BRAND, CODE_STANDARDS, PROCESS, SPEC, STATUS,
  TECH_STACK, PLAN.

## Backtest baseline (Phase 1)

`python -m revenue_analyst.backtest` on the seeded history: 3 properties ×
Jan–Oct 2026 × lead 30/60/90 days = 90 decisions; 30 windows actually ended
behind last year (final occupancy < 90% of LY).

| Rule | Flags | Precision | Recall | Accuracy |
|---|---|---|---|---|
| Fixed 40% (old) | 85 | 33% | 93% | 34% |
| Last year, same lead time (current) | 34 | 44% | 50% | 62% |

Reading: the benchmark stops the "flag everything" behaviour, but it is still
weak — "never flag" would score 67% accuracy. Signal is thin at 60–90 days and
for short-lead properties (Urban Boutique books ~14 days out: 0–4% on the
books vs 0–4% last year). Next levers: low-signal guard (Phase 1), more
history (Phase 1), pickup forecast (Phase 6).

## Known limitations

- No holiday/event awareness; moving holidays (Easter, Carnival,
  Thanksgiving) misalign with the 364-day shift.
- Pricing review only discounts in practice — it never proposes increases on
  dates pacing ahead.
- One benchmark per window; per-day last-year comparison is too sparse for
  small inventory.
- Single `min_rate` / `max_rate` all year; no seasonal min-stay rules.
- Pace endpoint, chat tool and dashboard don't show last-year comparison yet.
- Simulated data: lead time and cancellation rate don't vary by season;
  no holiday peaks.
- Mock rate publication is in-memory (restart restores generated rates).
- Pending reviews are tracked in process memory for de-duplication.

## Local environment notes

- The API needs an LLM key at startup (`OPENROUTER_API_KEY` in `.env`), even
  for GET endpoints.
- On the maintainer's machine port 8000 is taken by another process; the app
  runs on **8001**.

## Next

Merge PR #2 (Phase 0), then PR for the backtest (stacked on it). Remaining
Phase 1: low-signal guard, longer history, seasonal evals.
