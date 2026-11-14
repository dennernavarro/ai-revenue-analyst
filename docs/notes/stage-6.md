# Stage 6 — Deep Agents

**Built:** `agents/v3_deep.py` — `create_deep_agent` (deepagents 0.7.x,
pinned `<0.8` because the API moves between minors) with two subagents
(performance-analyst, pacing-analyst) and the shared tool belt. Exposed via
`cli.py --deep`.

**What deepagents adds:** `write_todos` (planning), `task()` (subagents with
isolated context), and a virtual filesystem (`write_file` etc.) as scratch
space.

**The honest findings** (same portfolio-review task, plain vs deep):

- With all tools available to the lead and a task that fits in one context,
  *neither gpt-4o-mini nor claude-haiku-4.5 delegated anything* — both just
  called the tools directly, producing traces nearly identical to the plain
  agent, at higher cost. Even when explicitly told to delegate, gpt-4o-mini
  skipped `task()` (it did use `write_file` for its report).
- That is not a deepagents bug; it's the design lesson: **subagents earn
  their cost only when (a) the work doesn't fit one context window, or
  (b) the lead is *forced* to delegate because it doesn't hold the tools
  itself.** Giving the lead the full tool belt made delegation optional, so
  capable models correctly skipped the ceremony.
- Design lever for later: strip the lead down to `task()` + filesystem only
  and give domain tools exclusively to subagents — delegation then becomes
  the only path. Worth doing when tasks grow (e.g. a 12-month, per-month
  review across many properties).
- A stronger model (claude-haiku) used the tools more cleverly — when the
  62-day rates cap bit, it split Q1 into two windows and covered the whole
  quarter, where gpt-4o-mini silently analyzed Jan–Feb only. Model quality
  shows up as *strategy*, not just prose.

**Takeaway:** reach for a deep agent when the task outgrows one context;
until then `create_agent` is cheaper, faster and easier to debug.
