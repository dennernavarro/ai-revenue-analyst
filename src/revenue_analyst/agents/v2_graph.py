"""Stage 4 agent: the SAME loop as v1, built by hand with LangGraph.

This is what create_agent was hiding:

        START → model ──(tool_calls?)──→ tools ──→ model → ... → END

Three ideas carry the whole framework:

1. **State** — a dict schema the graph threads through every node.
   MessagesState is just `{"messages": list}` with an `add_messages` reducer:
   nodes return only NEW messages and the reducer appends them, which is why
   each node below returns `{"messages": [...]}` instead of the full list.
2. **Nodes and edges** — nodes are plain functions `state -> partial state`;
   a conditional edge is a function that names the next node. The agent
   "loop" is literally the `tools → model` edge pointing back.
3. **Checkpointer** — persistence is orthogonal to the graph. Compile with a
   checkpointer and every step is saved under a thread_id; pass only the new
   message on the next turn and the history is already there. SQLite makes
   conversations survive a process restart (Stage 3's pain, fixed).

Run the CLI with `--agent v1` and `--agent v2` on the same question: the
behavior is identical, which is the point.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, MessagesState, StateGraph

from revenue_analyst.agents.v1_react import SYSTEM_PROMPT
from revenue_analyst.llm import init_model
from revenue_analyst.pms.provider import PMSProvider
from revenue_analyst.tools import build_tools


def sqlite_checkpointer(state_dir: Path) -> SqliteSaver:
    """A file-backed checkpointer: conversations survive process restarts."""
    state_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(state_dir / "checkpoints.sqlite", check_same_thread=False)
    return SqliteSaver(conn)


def build_agent(
    pms: PMSProvider,
    as_of: datetime,
    model: str | BaseChatModel = "openrouter:openai/gpt-4o-mini",
    checkpointer: BaseCheckpointSaver | None = None,
):
    if isinstance(model, str):
        model = init_model(model)
    tools = build_tools(pms, as_of)
    tools_by_name = {t.name: t for t in tools}
    model_with_tools = model.bind_tools(tools)
    system = SystemMessage(SYSTEM_PROMPT.format(as_of=as_of.date().isoformat()))

    def call_model(state: MessagesState) -> dict:
        """One LLM step: full history in, one new AIMessage out."""
        response = model_with_tools.invoke([system, *state["messages"]])
        return {"messages": [response]}

    def run_tools(state: MessagesState) -> dict:
        """Execute every tool call from the last AIMessage; each result goes
        back as a ToolMessage linked by tool_call_id."""
        last = state["messages"][-1]
        results = []
        for call in last.tool_calls:
            output = tools_by_name[call["name"]].invoke(call["args"])
            results.append(
                ToolMessage(
                    content=json.dumps(output),
                    name=call["name"],
                    tool_call_id=call["id"],
                )
            )
        return {"messages": results}

    def should_continue(state: MessagesState) -> str:
        last = state["messages"][-1]
        return "tools" if getattr(last, "tool_calls", None) else END

    graph = StateGraph(MessagesState)
    graph.add_node("model", call_model)
    graph.add_node("tools", run_tools)
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", should_continue)
    graph.add_edge("tools", "model")
    return graph.compile(checkpointer=checkpointer)
