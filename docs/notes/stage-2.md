# Stage 2 — First agent (create_agent)

**Built:** `agents/v1_react.py` (LangChain's `create_agent` over the Stage 1
tools) and `cli.py`, a terminal chat with manual conversation memory.

**What I learned**

- An "agent" at this level is just a loop: model proposes a tool call → the
  runtime executes it → the result goes back as a `ToolMessage` → repeat
  until the model answers in text. `create_agent` compiles that loop to a
  LangGraph graph under the hood.
- *The model is configuration.* `llm.init_model` resolves `RA_MODEL`; the
  custom `openrouter:<vendor>/<model>` scheme is just ChatOpenAI with
  OpenRouter's base_url, because OpenRouter speaks the OpenAI API — a useful
  trick: "OpenAI-compatible" providers don't need their own integration.
- *Agents can be unit-tested without an LLM.* `tests/test_agent_v1.py` injects
  a scripted fake model (its script already contains tool calls), proving the
  loop executes tools and feeds results back — offline and deterministic.
- Memory, Stage 2 style: keep the message list yourself and resend it every
  turn. It works, and it's exactly the pain LangGraph checkpointers remove in
  Stage 4.
- LangSmith tracing is just env vars (`LANGSMITH_TRACING=true` + key): no code
  changes, and the trace shows every model call, tool call and token count.
