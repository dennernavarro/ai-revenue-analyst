# Status

_Last updated: 2026-11-17_

**Version:** 1.1.0 (`main` @ `23c8770`) + unmerged work below.
**Phase:** 0 — foundation (see PLAN.md).

## Working

- Mock PMS with 3 properties (Seaside Villa, Urban Boutique, Mountain Cabins),
  seeded history 2025-01-01 → 2027-03-31, "today" 2026-11-01.
- Deterministic analytics, REST API, dashboard at `/ui`, chat agent, deep
  agent, pricing review with human approval and rate publication.
- Tests: 56 passed, 7 skipped (offline). Ruff clean. CI on GitHub Actions.
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

Phase 0 wrap-up (commit), then Phase 1 — backtesting and seasonal evals.
