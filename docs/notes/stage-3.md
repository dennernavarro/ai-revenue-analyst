# Stage 3 — FastAPI

**Built:** `api.py` — an app factory with three plain REST endpoints
(`/properties`, `.../performance`, `.../pace`) and one agent endpoint
(`POST /chat` with per-conversation memory).

**What I learned**

- *Draw the LLM boundary in the API surface.* Performance and pace are
  deterministic — serving them through the agent would add latency, cost and
  nondeterminism for nothing. Only `/chat` pays the LLM tax.
- *App factory > module-level app.* `create_app(pms=..., model=...)` lets
  tests inject the mock PMS and a scripted fake model; uvicorn runs it with
  `--factory`. The whole API suite runs offline.
- Extracting `booking_pace` from the tool closure into `analytics.py` let the
  REST endpoint and the agent tool share one implementation — the
  deterministic core grows, tools and endpoints stay thin.
- Conversation memory is still a dict in the process: restart the server and
  every conversation is gone, and two workers would not share state. That
  pain is the setup for Stage 4 (LangGraph checkpointing).
