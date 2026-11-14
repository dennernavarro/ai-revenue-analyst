# Stage 5 — LangGraph control flow

**Built:** `agents/pricing_review.py` — a pricing-review workflow with
deterministic routing, one structured LLM slot, a policy clamp, and a
human-approval interrupt. Exposed in the terminal (`python -m
revenue_analyst.review`) and over HTTP (`POST /reviews` + `.../decision`).

**What I learned**

- *Workflows invert agents.* In v1/v2 the model drives and tools serve it;
  here the graph drives and the model fills one slot with a schema
  (`with_structured_output(RateProposal)`). Most business processes want this
  shape, not an open-ended agent.
- *Route with thresholds, not vibes.* "Is this window pacing badly?" is a
  number comparison in Python. The healthy path never touches the LLM — the
  test proves it by making any LLM call raise.
- *Hard constraints live outside the model.* The clamp node caps ±25%
  whatever the LLM proposes. Tested with a scripted -60% proposal.
- *interrupt() = the paused graph is a checkpoint.* Resume with
  `Command(resume=...)` from the same process (CLI) or another one entirely
  (the API decision endpoint, maybe days later). Human-in-the-loop falls out
  of persistence for free.
- *Keep checkpointed state plainly serializable.* Storing the RateProposal
  object in state made the checkpointer warn about deserializing custom
  types; storing `model_dump()` dicts fixed it.
- Live run: the real model proposed -15% for December grounded in "20.16% on
  the books vs 79.84% same window last year" — the analysis JSON we fed it.
