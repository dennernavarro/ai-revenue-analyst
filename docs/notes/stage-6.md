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

## Postscript: pulling the forced-delegation lever

We later rebuilt v3 with the lead holding NO domain tools (only write_todos,
task and the filesystem) — lever (b) above. Delegation immediately became
real: the portfolio review produced a todo plan and six parallel task()
calls (one pacing + one performance dive per property), each in an isolated
context, with the lead synthesizing the reports.

Two new lessons came with it:

- *Multi-hop numbers play telephone.* The lead can garble figures while
  rewriting subagent reports (we watched one summary mix a nights count into
  an occupancy line). With a single agent, the number goes tool → answer;
  with delegation it goes tool → subagent prose → lead prose. Structured
  subagent outputs (response_format) would be the fix at scale.
- *Parallel subagents stress the plumbing.* One run died inside LangGraph's
  executor ("cannot schedule new futures after shutdown") with six
  concurrent task() calls over the SQLite checkpointer; later runs were
  clean. Concurrency bugs live at the infrastructure layer, not the prompt
  layer.
