"""The hand-built LangGraph agent must behave like v1 — plus persistence."""

import sqlite3
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from revenue_analyst.agents.v2_graph import build_agent
from revenue_analyst.datagen import AS_OF
from revenue_analyst.pms.mock import MockPMS

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

TOOL_CALL_SCRIPT = [
    AIMessage(
        content="",
        tool_calls=[{"name": "list_properties", "args": {}, "id": "call_1", "type": "tool_call"}],
    ),
    AIMessage(content="We manage 3 properties."),
]


def test_graph_runs_the_same_loop_as_v1(scripted_model):
    """Same scripted scenario as test_agent_v1 — the hand-built graph must
    execute the tool and feed the result back, just like create_agent."""
    agent = build_agent(MockPMS(DATA_DIR), AS_OF, model=scripted_model(TOOL_CALL_SCRIPT))
    result = agent.invoke({"messages": [HumanMessage("How many properties?")]})
    messages = result["messages"]

    tool_results = [m for m in messages if isinstance(m, ToolMessage)]
    assert len(tool_results) == 1
    assert "seaside-villa" in tool_results[0].content
    assert messages[-1].content == "We manage 3 properties."


def test_checkpointer_keeps_history_per_thread(scripted_model):
    script = [AIMessage(content="First answer."), AIMessage(content="Second answer.")]
    agent = build_agent(
        MockPMS(DATA_DIR), AS_OF, model=scripted_model(script), checkpointer=InMemorySaver()
    )
    config = {"configurable": {"thread_id": "t1"}}

    agent.invoke({"messages": [HumanMessage("First question")]}, config)
    # Only the new message is sent; the checkpointer supplies the rest.
    result = agent.invoke({"messages": [HumanMessage("Second question")]}, config)

    contents = [m.content for m in result["messages"]]
    assert contents == ["First question", "First answer.", "Second question", "Second answer."]

    # A different thread starts empty.
    assert agent.get_state({"configurable": {"thread_id": "other"}}).values == {}


def test_conversation_survives_a_process_restart(scripted_model, tmp_path):
    """The Stage 4 checkpoint: same SQLite file, brand-new agent instance
    (simulating a restart) — the old conversation is still there."""
    db = tmp_path / "checkpoints.sqlite"
    config = {"configurable": {"thread_id": "cli"}}

    first_conn = sqlite3.connect(db, check_same_thread=False)
    agent = build_agent(
        MockPMS(DATA_DIR), AS_OF,
        model=scripted_model([AIMessage(content="Noted: focus on December.")]),
        checkpointer=SqliteSaver(first_conn),
    )
    agent.invoke({"messages": [HumanMessage("Let's focus on December.")]}, config)
    first_conn.close()  # "process exits"

    reborn = build_agent(
        MockPMS(DATA_DIR), AS_OF,
        model=scripted_model([AIMessage(content="Still focused on December.")]),
        checkpointer=SqliteSaver(sqlite3.connect(db, check_same_thread=False)),
    )
    restored = reborn.get_state(config).values["messages"]
    assert [m.content for m in restored] == [
        "Let's focus on December.",
        "Noted: focus on December.",
    ]

    result = reborn.invoke({"messages": [HumanMessage("What are we focused on?")]}, config)
    assert result["messages"][-1].content == "Still focused on December."
    assert len(result["messages"]) == 4
