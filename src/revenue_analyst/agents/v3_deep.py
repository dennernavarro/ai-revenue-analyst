"""Stage 6 (revisited): a deep agent with FORCED delegation.

The first version gave the lead agent the full tool belt — and the Stage 6
experiment showed that capable models then correctly skip the ceremony:
no write_todos, no task(), traces identical to the plain agent at higher
cost. The lesson was recorded as a design lever:

    subagents earn their cost when (a) the work doesn't fit one context, or
    (b) the lead CANNOT do the work itself because it doesn't hold the tools.

This version pulls lever (b). The lead holds NO domain tools — only the
deepagents built-ins (write_todos, task, the virtual filesystem). Every
number must come back from a subagent report, so planning and delegation are
the only way to answer:

    lead (no tools) ── task() ──> performance-analyst (list, performance)
                   ── task() ──> pacing-analyst (list, pace, rates)

Each task() call runs in an ISOLATED context: a subagent can burn thousands
of tokens on tool results, and only its final summary returns to the lead.
That is the whole point of the architecture — watch the ⚙ trace in the CLI
to see it happen.

deepagents is still 0.x and its API moves between minors; pyproject pins the
minor version for that reason.
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
properties. You have NO data tools of your own: every number must come from
your subagents, so your job is to plan, delegate and synthesize.

1. Plan first with write_todos and keep the plan updated as you go.
2. Delegate with task(): performance-analyst for realized results,
   pacing-analyst for future windows — one focused task per property and
   window, with precise property ids and ISO date ranges in the task
   description.
3. Collect the reports and write the final answer yourself: lead with the
   portfolio-level conclusion, then per-property evidence, then recommended
   next steps. Quote only numbers your subagents reported.

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
            "tools": [
                by_name["list_properties"],
                by_name["get_booking_pace"],
                by_name["get_rates"],
            ],
        },
    ]

    return create_deep_agent(
        model=model,
        tools=[],  # forced delegation: the lead cannot touch data itself
        system_prompt=LEAD_PROMPT.format(rules=rules),
        subagents=subagents,
        checkpointer=checkpointer,
    )
