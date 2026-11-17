# Code standards

The rules this codebase already follows. New code follows them too; a PR that
breaks one says why.

## Architecture rules

1. **Tools calculate, agents reason.** KPIs (occupancy, ADR, RevPAR, pace)
   live in pure, tested functions in `analytics.py`. Agents call tools; they
   never compute figures. Prompts forbid model arithmetic.
2. **Hard constraints live in code, outside the LLM.** Rate bounds (±25% per
   review, property min/max rate), approval gates and routing decisions are
   Python. The LLM fills one well-defined, schema-typed slot
   (`with_structured_output`).
3. **GET endpoints never touch the LLM.** Only `/chat`, `/chat/stream` and
   `/reviews` do.
4. **The PMS is a port.** Everything reads through `PMSProvider` and writes
   through the separate `RatePublisher`. New PMS = copy `pms/template.py`,
   register in `pms/factory.py`, pass `tests/test_pms_contract.py`.
5. **Date ranges are half-open** (`end` excluded). A full month ends on the
   1st of the next month. Applies to analytics, tools, API and prompts.
6. **Time is injected.** "Now" is an `as_of` argument. Only entry points
   (`api.py`, `cli.py`, `review.py`) resolve it, from the PMS data or
   `datetime.now()`; analytics, tools and agents never read the clock — that's
   what makes pace and tests deterministic.
7. **Checkpointed state is plain data** (dicts, ISO strings), not custom
   classes.

## Python

- Python ≥ 3.11, `from __future__ import annotations` at the top of modules.
- `ruff check .` must pass (line length 100). No other formatter is enforced;
  match surrounding style.
- Pydantic models for domain types and API schemas; `TypedDict` for graph
  state.
- Business constants are module-level `UPPER_CASE` with a docstring saying
  what they mean and why the value (see `pricing_review.py`).
- Docstrings and comments explain **why**, not what. Module docstrings state
  the lesson/role of the module.
- Errors the agent can recover from (unknown property, bad range) are returned
  as clear messages, not raised into the loop.
- No secrets in code or tests. Keys come from `.env` (git-ignored).
- Deliberate shortcuts with a known ceiling get a `ponytail:` comment naming
  the ceiling and the upgrade path.

## Tests

- `uv run pytest` runs **fully offline**: agents use the scripted fake model
  in `tests/conftest.py`; no network, no API key.
- Mock data is deterministic (seeded). Tests may assert exact numbers from
  `data/*.json`; comment where a number comes from.
- Every behaviour change to pricing, pace or analytics ships with a test that
  fails without it.
- Model quality is not a unit test — it belongs in `evals.py` (ground truth
  computed from `analytics.py`, never hand-written).

## Frontend

- React 18 function components + hooks, plain CSS with the tokens in
  `styles.css` (see BRAND.md). No component library, no CSS framework.
- All API calls go through `frontend/src/api.js`.
- The UI only displays numbers the API returned — no client-side KPI math.

## Naming

- Property IDs are kebab-case slugs (`seaside-villa`).
- Agent modules are versioned by stage (`v1_react.py`, `v3_deep.py`); the
  workflow is `pricing_review.py`.
- Commit messages: Conventional Commits (see PROCESS.md).
