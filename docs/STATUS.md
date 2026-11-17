# Status

_Last updated: 2026-11-17_

**Version:** 1.1.0 (`main` @ `23c8770`) + three stacked, unmerged PRs below.
**Phase:** 1 and 2 in progress; calendar redesign and Auto-pilot designed (see PLAN.md).

## Working

- Mock PMS with 3 properties (Seaside Villa, Urban Boutique, Mountain Cabins),
  seeded history 2025-01-01 → 2027-03-31, "today" 2026-11-01, with holidays
  and local events baked into demand, rates and lead times.
- Deterministic analytics, REST API, dashboard at `/ui`, chat agent, deep
  agent, pricing review with human approval and rate publication.
- Tests: 61 passed, 8 skipped (offline). Ruff clean. CI on GitHub Actions.
- Verified live with OpenRouter (`gpt-4o-mini`): chat answers match the KPI
  tiles; reviews route as expected on the current data.

## Unmerged work (stacked: each PR builds on the previous)

1. **PR #2 — Phase 0** (`feat/season-aware-pricing-review`): the review
   benchmarks against last year's on-the-books at the same lead time (90%
   tolerance); fixed 40% only without history. Project docs in `docs/`.
2. **PR #3 — Phase 1 backtest** (`feat/backtest`):
   `python -m revenue_analyst.backtest`; the routing rule is one pure
   function shared by review and backtest.
3. **Phase 2 events** (`feat/events-calendar`): holiday/event calendar,
   simulator effects, `PMSProvider.get_events`, holiday-aligned last-year
   comparison (Easter 2027 ↔ Easter 2026 = 357 days), `event_aligned`
   backtest rule. Mock data regenerated — test fixtures moved accordingly.

Live reviews on the current data:

| Window | Booked now vs last year by now | Outcome |
|---|---|---|
| Mountain Cabins Dec 2026 | 30% vs 24% | No action (old fixed 40% would discount) |
| Mountain Cabins Mar 2027 | 2% vs 7% | −15% on 29 nights |
| Seaside Villa Mar 2027 (Easter-aligned) | 3% vs 30% | −15% on 30 nights |

## Backtest (Phase 1, current data with events)

`python -m revenue_analyst.backtest`: 3 properties × Jan–Oct 2026 × lead
30/60/90 days = 90 decisions; 45 windows ended behind last year (final
occupancy < 90% of last year's). Accuracy by how "last year" is defined:

| Rule | Flags | Precision | Recall | Accuracy (364-day truth) | Accuracy (event-aligned truth) |
|---|---|---|---|---|---|
| Fixed 40% (old) | 89 | 51% | 100% | 51% | 51% |
| Last year, 364 days | 32 | 56% | 40% | 54% | 54% |
| Last year, event-aligned (current) | 37 | 57% | 47% | 56% | 60% |

Precision/recall shown against the 364-day truth. Reading: the benchmark
stops the "flag everything" behaviour; event alignment adds a little (only 7
of 30 months shift). Monthly occupancy is very noisy for small inventory
(Mountain Cabins March: 36% in 2025, 85% in 2026), so differences of a few
points are within noise. Next levers: low-signal guard and longer history
(Phase 1), night-level checks (Phase 4), pickup forecast (Phase 7).

Before the events data (old baseline): fixed 40% 34% accuracy, last year 62%
— not comparable with the table above (different data, 30 vs 45 behind).

## Known limitations

- Pricing review only discounts in practice — it never proposes increases on
  dates pacing ahead.
- One benchmark per window: a slow night inside a healthy month is never
  flagged (e.g. Seaside Villa's empty Christmas nights while December is
  ahead). Night-level checks are Phase 4.
- The model's rationale can misstate comparisons ("$275 is significantly
  above $290", "0.0 booked last year" when it was high); no fact check yet.
- Single `min_rate` / `max_rate` all year; no seasonal min-stay rules.
- Simulator: event uplift publishes rates above `max_rate` (Mountain Cabins
  Christmas $655 > $432); low-season rates fall below `min_rate` (Seaside
  Villa January $176 < $192). Cancellation rate doesn't vary by season.
- Events API endpoint and chat tool not built yet; calendar UI still the old
  design (new one in Claude Design, "Revenue Calendar Redesign").
- Mock rate publication and pending reviews live in process memory.

## Local environment notes

- The API needs an LLM key at startup (`OPENROUTER_API_KEY` in `.env`), even
  for GET endpoints.
- Port 8000 was taken by another local process earlier; the app falls back to
  8001 when that happens.

## Next

Merge PRs in order (#2 → #3 → Phase 2). Finish Phase 2: events tool and
endpoint, calendar UI per the approved design. Then the night-level backtest,
which gates Auto-pilot (Phase 4).
