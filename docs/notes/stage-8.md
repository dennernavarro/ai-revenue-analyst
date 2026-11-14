# Stage 8 — Evaluation

**Built:** `evals.py` — a behavioral eval suite for the agent, runnable
locally (`python -m revenue_analyst.evals`) and as a LangSmith experiment
(`--langsmith`).

**What I learned**

- *Compute the ground truth, don't write it.* Every expected number in the
  dataset comes from `analytics.py` over the seeded data — the same functions
  the tools use. The dataset cannot drift out of sync with the simulator, and
  `tests/test_evals.py` asserts that equivalence.
- *Evaluate behavior, not prose.* Three cheap programmatic evaluators beat an
  LLM judge for this job: key numbers present within tolerance, expected
  tools actually called, and full-month questions using half-open windows
  (end date = 1st of next month) — written specifically because we watched
  gpt-4o-mini get that wrong live in Stage 2.
- *First run: 8/9.* The failure was the best part: asked for December
  capacity and sales, the agent did 12 units × 31 nights in its head and
  never called `get_booking_pace` — mental math instead of tools, precisely
  the policy the system prompt forbids. A prose reviewer would have praised
  that answer; the tools evaluator flagged it.
- Trap questions earn their place: unknown property (must recover and name
  real ones) and future occupancy (must report on-the-books, not predict)
  both passed — evidence the recoverable-error design and the system prompt
  rules actually hold.
- The LangSmith path reuses the same scoring function as a `(inputs,
  outputs, reference_outputs)` evaluator — write scorers as pure functions
  and every harness can host them.
