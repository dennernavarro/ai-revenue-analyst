# AI Revenue Analyst

A small, open-source learning project: an AI revenue analyst for short-term
rentals and boutique hotels, built step by step to learn modern agent
development with **LangChain**, **LangGraph**, **Deep Agents**, **LangSmith**,
**FastAPI**, and **Docker**.

This is a learning project, not a production revenue management system.

## Design principles

- **Tools calculate, agents reason.** Occupancy, ADR, RevPAR and booking pace
  are deterministic Python functions ([analytics.py](src/revenue_analyst/analytics.py)).
  Agents call them as tools and never invent numbers.
- **Replaceable PMS seam.** Everything depends on the `PMSProvider` protocol
  ([pms/provider.py](src/revenue_analyst/pms/provider.py)). Today a mock reads
  JSON files; a real PMS later is one new adapter class that passes the same
  contract tests.
- **Simulated bookings, not invented percentages.** The mock data is produced
  by simulating booking *arrivals* (seasonal demand, lead times, lengths of
  stay, cancellations, lost demand when sold out), so occupancy, pace and gaps
  are internally consistent ([datagen.py](src/revenue_analyst/datagen.py)).
- **Each framework is introduced only when the previous one hurts.**

## Quickstart

```bash
# with uv
uv sync
uv run pytest
uv run python scripts/demo_report.py

# or with plain venv/pip
python3 -m venv .venv && .venv/bin/pip install pydantic pydantic-settings pytest ruff
.venv/bin/pytest
PYTHONPATH=src .venv/bin/python scripts/demo_report.py
```

Regenerate the mock datasets (deterministic — same seeds, same output):

```bash
PYTHONPATH=src python scripts/generate_data.py
```

## Chat with the analyst (Stage 2+)

```bash
cp .env.example .env   # add your OPENROUTER_API_KEY
uv run python -m revenue_analyst.cli
uv run python -m revenue_analyst.cli --once "How was August 2026 at Seaside Villa vs the other properties?"
```

The model is configuration, not code: `RA_MODEL` defaults to Claude Haiku via
OpenRouter (`openrouter:<vendor>/<model>` works for any model there, since
OpenRouter speaks the OpenAI API), and direct-provider strings like
`anthropic:claude-haiku-4-5` or `ollama:llama3.2` also work — see
[llm.py](src/revenue_analyst/llm.py). To see full agent traces, uncomment the
`LANGSMITH_*` variables in `.env` — tracing is optional and everything works
without it.

## REST API (Stage 3+)

```bash
uv run uvicorn revenue_analyst.api:create_app --factory --reload
```

- `GET /properties`
- `GET /properties/{id}/performance?start=2026-08-01&end=2026-09-01`
- `GET /properties/{id}/pace?start=2026-12-01&end=2027-01-01`
- `POST /chat` — `{"message": "...", "conversation_id": "optional"}`

Interactive docs at http://127.0.0.1:8000/docs. The GET endpoints never touch
the LLM; only `/chat` does — that boundary is the point.

## Learning roadmap

| Stage | Topic | Status |
|---|---|---|
| 0 | Foundation: domain, mock PMS, simulator, analytics (no LLM) | ✅ |
| 1 | LangChain tools over the analytics layer | ✅ |
| 2 | First agent: `create_agent` + CLI chat + LangSmith tracing | ✅ |
| 3 | FastAPI: `/chat` plus plain REST endpoints | ✅ |
| 4 | LangGraph basics: explicit graph, state, checkpointing | ⬜ |
| 5 | LangGraph control flow: routing, human-in-the-loop approval | ⬜ |
| 6 | Deep Agents: planning, subagents, when they earn their cost | ⬜ |
| 7 | Docker: containerized deployment | ⬜ |
| 8 | LangSmith evaluation: datasets, evaluators, regression runs | ⬜ |

Agent versions are kept side by side in `src/revenue_analyst/agents/`
(`v1_react.py`, `v2_graph.py`, `v3_deep.py`) so the progression stays readable.

## Mock properties

Three seeded properties with different demand patterns (as of the simulated
"today", 2026-11-01):

- **Seaside Villa** — single-unit vacation rental, summer-peaked, long stays,
  long lead times.
- **Urban Boutique** — 12-room city hotel, weekday business demand, short
  stays, short lead times.
- **Mountain Cabins** — 4 cabins, winter-peaked weekend leisure demand.
