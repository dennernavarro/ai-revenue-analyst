"""Stage 5: run a pricing review with human approval in the terminal.

    uv run python -m revenue_analyst.review mountain-cabins 2026-12-01 2027-01-01

If the window is pacing below target, the workflow proposes a rate adjustment
and PAUSES (LangGraph interrupt). You approve or reject; the paused state
lives in the checkpointer, so the decision could just as well come hours
later or from another process (see POST /reviews in the API).
"""

from __future__ import annotations

import argparse
import uuid
from datetime import date

from dotenv import load_dotenv
from langgraph.types import Command

from revenue_analyst.agents.pricing_review import build_pricing_review
from revenue_analyst.config import Settings
from revenue_analyst.persistence import sqlite_checkpointer
from revenue_analyst.pms.mock import MockPMS


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Pricing review with human approval")
    parser.add_argument("property_id")
    parser.add_argument("start", type=date.fromisoformat)
    parser.add_argument("end", type=date.fromisoformat)
    args = parser.parse_args()

    settings = Settings()
    pms = MockPMS(settings.data_dir)
    as_of = pms.as_of(pms.list_properties()[0].id)
    workflow = build_pricing_review(
        pms,
        as_of,
        model=settings.model,
        checkpointer=sqlite_checkpointer(settings.state_dir),
        publisher=pms if settings.rate_publication else None,
    )
    config = {"configurable": {"thread_id": f"review-{uuid.uuid4().hex[:8]}"}}

    result = workflow.invoke(
        {"property_id": args.property_id, "start": args.start, "end": args.end}, config
    )
    if "__interrupt__" not in result:
        print(result["outcome"])
        return

    payload = result["__interrupt__"][0].value
    proposal = payload["proposal"]
    print("\nProposal awaiting approval")
    print(f"  window:     {payload['window']['start']} → {payload['window']['end']}")
    print(f"  on books:   {payload['on_the_books']}")
    print(f"  adjustment: {proposal['adjustment_pct']:+.1f}% on published rates")
    print(f"  rationale:  {proposal['rationale']}")
    print(f"  expected:   {proposal['expected_effect']}")

    answer = input("\nApprove? [y/N] ").strip().lower()
    note = input("Note (optional): ").strip()
    result = workflow.invoke(
        Command(resume={"approved": answer == "y", "note": note}), config
    )
    print("\n" + result["outcome"])


if __name__ == "__main__":
    main()
