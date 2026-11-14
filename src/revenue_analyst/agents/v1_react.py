"""Stage 2 agent: the prebuilt tool-calling loop, via LangChain's create_agent.

create_agent wires the classic agent loop for you (it compiles to a LangGraph
graph under the hood):

    model → wants a tool? → run tool → feed result back → ... → final answer

That loop is all an "agent" is at this stage. In Stage 4 we rebuild it by hand
with LangGraph to see the state machine inside; keeping this version around
makes the comparison concrete.

`model` accepts either a provider string (resolved by llm.init_model, so the
LLM vendor is a config value, not an import) or an already-built chat model —
which is how tests inject a scripted fake model and run the loop offline.
"""

from __future__ import annotations

from datetime import datetime

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel

from revenue_analyst.llm import init_model
from revenue_analyst.pms.provider import PMSProvider
from revenue_analyst.tools import build_tools

SYSTEM_PROMPT = """\
You are an AI revenue analyst for short-term rentals and small hotels.
The simulated "today" is {as_of}: dates before it are history, dates after it
are the future (bookings are still arriving for them).

Rules:
- Every number you state must come from a tool result. Never estimate,
  extrapolate or invent figures.
- Tool date ranges are half-open: end_date is excluded, so full August 2026
  is 2026-08-01 to 2026-09-01.
- Occupancy from tools is a fraction (0..1); present it as a percentage.
- If the property is ambiguous, call list_properties and ask the user.
- Be concise: lead with the answer, then the supporting numbers.
"""


def build_agent(
    pms: PMSProvider,
    as_of: datetime,
    model: str | BaseChatModel = "openrouter:anthropic/claude-haiku-4.5",
):
    if isinstance(model, str):
        model = init_model(model)
    return create_agent(
        model,
        build_tools(pms, as_of),
        system_prompt=SYSTEM_PROMPT.format(as_of=as_of.date().isoformat()),
    )
