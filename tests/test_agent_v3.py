"""Plumbing test for the deep agent: it builds with our tools and subagents
and completes a run with a scripted model. Quality of planning/delegation is
eval territory (Stage 8), not unit-test territory."""

from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage

from revenue_analyst.agents.v3_deep import build_deep_agent
from revenue_analyst.datagen import AS_OF
from revenue_analyst.pms.mock import MockPMS

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def test_deep_agent_builds_and_answers(scripted_model):
    agent = build_deep_agent(
        MockPMS(DATA_DIR), AS_OF, model=scripted_model([AIMessage(content="Portfolio looks fine.")])
    )
    result = agent.invoke({"messages": [HumanMessage("Quick check, no tools needed.")]})
    assert result["messages"][-1].content == "Portfolio looks fine."
