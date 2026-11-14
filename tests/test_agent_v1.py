"""The agent loop is tested WITHOUT any LLM.

A scripted fake model first "decides" to call a tool, then gives a final
answer. If the test passes, create_agent really executed our tool and fed the
result back — the whole loop works offline, deterministically, for free.
This is the pattern for agent unit tests; real-model quality tests come in
Stage 8 with LangSmith evaluations.
"""

from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from revenue_analyst.agents.v1_react import build_agent
from revenue_analyst.datagen import AS_OF
from revenue_analyst.pms.mock import MockPMS

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def test_agent_executes_tools_and_answers(scripted_model):
    script = [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "list_properties", "args": {}, "id": "call_1", "type": "tool_call"}
            ],
        ),
        AIMessage(content="We manage 3 properties."),
    ]
    agent = build_agent(MockPMS(DATA_DIR), AS_OF, model=scripted_model(script))

    result = agent.invoke({"messages": [HumanMessage("How many properties do we manage?")]})
    messages = result["messages"]

    tool_results = [m for m in messages if isinstance(m, ToolMessage)]
    assert len(tool_results) == 1, "the agent should have executed exactly one tool"
    assert "seaside-villa" in tool_results[0].content

    assert messages[-1].content == "We manage 3 properties."
