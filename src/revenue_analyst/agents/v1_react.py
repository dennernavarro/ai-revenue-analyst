"""The chat agent: LangChain's create_agent over the read-only tools.

create_agent wires the classic tool-calling loop (it compiles to a LangGraph
graph under the hood):

    model → wants a tool? → run tool → feed result back → ... → final answer

Pass a checkpointer and the graph persists conversations per thread_id — in
Stage 4 we rebuilt this loop by hand to see that machinery (nodes, conditional
edge, reducer state); the hand-built version was then removed as redundant,
but the write-up survives in docs/notes/stage-4.md and the git history.

`model` accepts either a provider string (resolved by llm.init_model, so the
LLM vendor is a config value, not an import) or an already-built chat model —
which is how tests inject a scripted fake model and run the loop offline.
"""

from __future__ import annotations

from datetime import datetime

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver

from revenue_analyst.llm import init_model
from revenue_analyst.pms.provider import PMSProvider
from revenue_analyst.tools import build_tools

SYSTEM_PROMPT = """\
You are an AI revenue analyst for short-term rentals and small hotels.
The simulated "today" is {as_of}: dates before it are history, dates after it
are the future (bookings are still arriving for them).

Rules:
- Every number you state must come from a tool result. Never estimate,
  extrapolate or invent figures — and never do arithmetic yourself, not even
  trivial multiplication like units × nights: capacities, totals and shares
  are already in the tool results (get_booking_pace returns capacity_nights).
- Tool date ranges are half-open: end_date is excluded. A FULL MONTH always
  ends on the 1st of the NEXT month — December 2026 is 2026-12-01 to
  2027-01-01. An end_date on the 28th–31st silently drops the last night and
  is always wrong for a full month.
- Occupancy from tools is a fraction (0..1); present it as a percentage.
- If the property is ambiguous, call list_properties and ask the user.
- Be concise: lead with the answer, then the supporting numbers.
"""


def build_agent(
    pms: PMSProvider,
    as_of: datetime,
    model: str | BaseChatModel = "openrouter:openai/gpt-4o-mini",
    checkpointer: BaseCheckpointSaver | None = None,
):
    if isinstance(model, str):
        model = init_model(model)
    return create_agent(
        model,
        build_tools(pms, as_of),
        system_prompt=SYSTEM_PROMPT.format(as_of=as_of.date().isoformat()),
        checkpointer=checkpointer,
    )
