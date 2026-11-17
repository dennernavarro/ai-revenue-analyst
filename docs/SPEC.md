# Specification

What the AI Revenue Analyst does today, and the invariants any change must
keep. Planned behaviour lives in PLAN.md until it ships, then moves here.

## Users

- **Owner/host** of one or a few short-term rentals: wants plain answers and
  safe price suggestions.
- **Revenue manager** of a small hotel or portfolio: wants pace, gaps and
  multi-property analysis quickly, with control over every rate change.

## Domain

- **Property** with room types and units; `min_rate` / `max_rate` bounds.
- **Reservation**: check-in/out, `booked_at`, optional `cancelled_at`, status,
  channel, revenue.
- **Daily rate**: per day, rate + min-stay.
- **as_of**: the moment "now" (mock: 2026-11-01 12:00). Before it is history;
  after it, bookings are still arriving.

## Metrics (deterministic, `analytics.py`)

| Metric | Definition |
|---|---|
| Occupancy | nights sold / nights available in `[start, end)` |
| ADR | revenue / nights sold |
| RevPAR | revenue / nights available |
| On the books (OTB) | nights booked by `as_of` and not cancelled by `as_of` |
| Pace | OTB for a window at `as_of` and 30/60/90 days earlier |

## Capabilities

### Dashboard (`/ui`)
Property switcher, KPI row, month calendar (rate, min-stay, nights sold per
day), room-category occupancy, chat panel with tool activity, "Run pricing
review" with approve/decline cards and a calendar preview of affected dates.
**Deep** toggle switches the chat to the deep agent (amber theme).

### Chat agent
Answers questions using four read-only tools: `list_properties`,
`get_performance`, `get_booking_pace`, `get_rates`. Knows the selected
property and displayed month from the dashboard. Conversations persist per
thread.

### Deep agent
Lead agent holds **no data tools**; it must plan (`write_todos`) and delegate
(`task()`) to `performance-analyst` and `pacing-analyst` subagents. For
multi-property / portfolio questions.

### Pricing review (human-in-the-loop)
For a property and window:

1. **Analyze** (deterministic): pace, published rates, rate limits, last
   year's final occupancy/ADR, and the **pace benchmark**:
   - With history: required share = 90% (`PACE_TOLERANCE`) of what the same
     window had on the books **at the same lead time last year** (364-day
     shift so weekdays align).
   - Without history: fixed 40% of capacity (`HEALTHY_OTB_SHARE`).
2. **Route**: not behind → "No action" summary. Behind but average rate
   already within 2% of `min_rate` → "No further discount" summary. Otherwise →
   propose.
3. **Propose** (LLM, structured `RateProposal`): one % adjustment with
   rationale and expected effect.
4. **Enforce**: clamp to ±25% (`MAX_ADJUSTMENT_PCT`).
5. **Human approval**: graph pauses (`interrupt`); can resume minutes or days
   later.
6. **Record**: rejected → nothing changes. Approved → applied only to
   **target days** (filled below the benchmark share), each clamped to
   `[min_rate, max_rate]`, published via `RatePublisher` (unless
   `RA_RATE_PUBLICATION=false`).

### REST API

| Endpoint | LLM | Purpose |
|---|---|---|
| `GET /properties` | no | List properties |
| `GET /properties/{id}/performance?start&end` | no | Occupancy, ADR, RevPAR, revenue |
| `GET /properties/{id}/pace?start&end` | no | Pace at 0/30/60/90 days back |
| `GET /properties/{id}/calendar?start&end` | no | Per-day rate, min-stay, nights sold |
| `GET /properties/{id}/room-types?start&end` | no | Categories, units, from-rate, occupancy |
| `POST /chat`, `POST /chat/stream` | yes | Chat; `conversation_id` continues a thread |
| `POST /reviews` | yes* | Start review → `no_action` or `pending_approval` (+ `target_days`) |
| `POST /reviews/{id}/decision` | no | Approve/reject once; 409 if already decided, 404 if unknown |

\* Only reached when the window is behind its benchmark.

Duplicate `POST /reviews` for the same pending window returns the same review.

### CLI
`python -m revenue_analyst.cli` (chat, `--deep`, `--thread`, `--once`) and
`python -m revenue_analyst.review <property> <start> <end>`.

## Invariants (must never break)

1. Every number shown to the user comes from a deterministic tool/endpoint.
2. No rate is published without explicit human approval, and a decision
   applies at most once.
3. Published rates stay within `[min_rate, max_rate]`; one review moves rates
   by at most ±25%.
4. Dates already selling at/above the benchmark (incl. sold out) keep their
   price.
5. GET endpoints never call an LLM.
6. Date ranges are half-open everywhere.
7. The test suite runs offline.

## Non-goals (for now)

- Automatic (unapproved) repricing.
- Multi-currency conversion, taxes, fees.
- Multi-tenant auth — the app assumes a single trusted operator.
