# Stage 1 — Tools

**Built:** `build_tools(pms, as_of)` → four read-only LangChain tools:
`list_properties`, `get_performance`, `get_booking_pace`, `get_rates`.

**What I learned**

- *The docstring is the interface.* The LLM sees only name + docstring +
  argument schema. Saying "dates are ISO, end_date is excluded, occupancy is
  0..1" in the docstring is prompt engineering with a compiler.
- *Dependency injection by closure.* The factory closes over a `PMSProvider`
  and a clock, so tools run over mock or real data unchanged, and tests can
  inject anything. No framework needed.
- *Tool errors should be recoverable.* An unknown property id returns
  `{"error": ..., "valid_property_ids": [...]}` instead of raising, so the
  agent can correct itself in the next step.
- `scripts/demo_tools.py` prints the toolbox exactly as the model sees it —
  worth running before writing any agent prompt.
