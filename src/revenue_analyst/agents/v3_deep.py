"""Stage 6: a deep agent — planning, subagents, context isolation.

What deepagents adds on top of create_agent:

- write_todos: the agent PLANS before acting and checks steps off as it goes.
- task(): spawns SUBAGENTS whose context is isolated — a per-property deep
  dive burns its own tokens and returns only a summary to the lead agent.
- A virtual filesystem (ls / read_file / write_file) as scratch space.

When is this worth it? For long-horizon, multi-step work where a single
context window would drown in tool results — "review Q1 for ALL properties
and recommend actions per property". For "how was August?", the plain agent
is strictly better: cheaper, faster, fewer moving parts. Run both on the same
big task (cli.py --deep) and compare the ⚙ traces — that comparison is the
lesson of this stage.

deepagents is still 0.x and its API moves between minors; pyproject pins
the minor version for that reason.
"""

from __future__ import annotations

from datetime import datetime

from deepagents import create_deep_agent
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver

from revenue_analyst.llm import init_model
from revenue_analyst.pms.provider import PMSProvider
from revenue_analyst.tools import build_tools

SHARED_RULES = """\
Numbers come ONLY from tool results — never invent, extrapolate or compute
figures yourself (capacity_nights is already in get_booking_pace results).
Tool date ranges are half-open: end_date is excluded, so a full month ends on
the 1st of the NEXT month (full August 2026 = 2026-08-01 to 2026-09-01,
never ...-08-31). The simulated "today" is {as_of}. Occupancy from tools is a
fraction (0..1); report it as a percentage."""

LEAD_PROMPT = """\
You are the LEAD revenue analyst for a portfolio of short-term rental
properties. For any non-trivial request:

1. Plan first with write_todos and keep the plan updated as you go.
2. Delegate the heavy lifting to your subagents — performance-analyst for
   realized results, pacing-analyst for future windows — one task per
   property, with precise property ids and ISO date ranges.
3. Collect their findings and write the final report yourself: lead with the
   portfolio-level conclusion, then per-property evidence, then recommended
   next steps.

For trivial single-number questions, skip the ceremony and call a tool
directly.

{rules}"""

PERFORMANCE_PROMPT = """\
You analyze the REALIZED performance of one property for the period you were
given: occupancy, ADR, RevPAR, revenue, and how periods compare. Return a
compact summary with the key numbers — no filler.

{rules}"""

PACING_PROMPT = """\
You analyze FUTURE stay windows for one property: booking pace (on the books
now vs 30/60/90 days ago), share of capacity sold, and published rates.
Say clearly whether the window looks healthy or at risk. Return a compact
summary with the key numbers — no filler.

{rules}"""


def build_deep_agent(
    pms: PMSProvider,
    as_of: datetime,
    model: str | BaseChatModel = "openrouter:openai/gpt-4o-mini",
    checkpointer: BaseCheckpointSaver | None = None,
):
    if isinstance(model, str):
        model = init_model(model)
    tools = build_tools(pms, as_of)
    by_name = {t.name: t for t in tools}
    rules = SHARED_RULES.format(as_of=as_of.date().isoformat())

    subagents = [
        {
            "name": "performance-analyst",
            "description": (
                "Deep dive on REALIZED performance (occupancy, ADR, RevPAR, revenue) "
                "for one property over past dates."
            ),
            "system_prompt": PERFORMANCE_PROMPT.format(rules=rules),
            "tools": [by_name["list_properties"], by_name["get_performance"]],
        },
        {
            "name": "pacing-analyst",
            "description": (
                "Deep dive on FUTURE stay windows for one property: booking pace, "
                "on-the-books vs capacity, published rates."
            ),
            "system_prompt": PACING_PROMPT.format(rules=rules),
            "tools": [by_name["get_booking_pace"], by_name["get_rates"]],
        },
    ]

    return create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=LEAD_PROMPT.format(rules=rules),
        subagents=subagents,
        checkpointer=checkpointer,
    )
