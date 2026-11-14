# Stage 4 — LangGraph by hand

**Built:** `agents/v2_graph.py` — the same agent as v1, but as an explicit
`StateGraph`: a `model` node, a `tools` node, a conditional edge, and a
checkpointer. CLI and API defaulted to it for a while.

**Postscript:** once the lesson was learned, v2 was deleted (see git history
for the implementation). `create_agent` accepts the same `checkpointer`
argument, so the one real capability — persistent conversations — moved back
to the one-liner agent, and the old SQLite threads kept working unchanged.
Keeping two implementations of the same loop was didactic debt, not value.

**What I learned**

- The whole "agent" is ~40 lines of graph: `START → model`, a conditional
  edge (`tool_calls? → tools : END`), and `tools → model` closing the loop.
  `create_agent` was never magic.
- *State is a reducer, not a variable.* Nodes return only their NEW messages;
  the `add_messages` reducer appends them. That convention is what makes
  checkpointing and resuming work.
- *Persistence is orthogonal to logic.* The graph doesn't know whether it has
  a checkpointer. Compile with `SqliteSaver` and suddenly: send only the new
  message per turn, history is loaded by `thread_id`, and conversations
  survive process restarts (verified live with two separate CLI processes —
  the second one recalled context with zero tool calls).
- The API's Stage 3 conversation dict was deleted, replaced by
  `thread_id = conversation_id`. Tests inject `InMemorySaver`; prod uses
  SQLite; Postgres would be the same one-line swap.
- `get_state(config)` is the debugging superpower: inspect any thread's
  full message history outside a run.
