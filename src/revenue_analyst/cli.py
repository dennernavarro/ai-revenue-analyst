"""Chat with the revenue analyst in your terminal.

    uv run python -m revenue_analyst.cli
    uv run python -m revenue_analyst.cli --once "How was August 2026 at Seaside Villa?"

Conversations persist in a SQLite checkpointer (.state/), keyed by --thread:
exit, come back, and the context is still there. The LLM comes from RA_MODEL;
set the LANGSMITH_* variables in .env for full traces.
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from revenue_analyst.agents.v1_react import build_agent
from revenue_analyst.config import Settings
from revenue_analyst.llm import message_text
from revenue_analyst.persistence import sqlite_checkpointer
from revenue_analyst.pms.mock import MockPMS


def _print_turn(new_messages: list[BaseMessage]) -> None:
    for message in new_messages:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                print(f"  ⚙ {call['name']}({call['args']})")
    print(f"\nanalyst> {message_text(new_messages[-1])}\n")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Chat with the AI revenue analyst")
    parser.add_argument("--once", metavar="QUESTION", help="ask one question and exit")
    parser.add_argument(
        "--thread", default="cli", help="conversation id for persistence (resume anytime)"
    )
    args = parser.parse_args()

    settings = Settings()
    key_vars = {
        "openrouter": "OPENROUTER_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
    }
    key_var = key_vars.get(settings.model.split(":", 1)[0])
    if key_var and not os.getenv(key_var):
        sys.exit(f"{key_var} is not set — copy .env.example to .env and add your key.")

    pms = MockPMS(settings.data_dir)
    as_of = pms.as_of(pms.list_properties()[0].id)
    agent = build_agent(
        pms, as_of, model=settings.model,
        checkpointer=sqlite_checkpointer(settings.state_dir),
    )
    config = {"configurable": {"thread_id": args.thread}}

    def ask(question: str) -> None:
        # The checkpointer owns the history: send ONLY the new message.
        previous = len(agent.get_state(config).values.get("messages", []))
        result = agent.invoke({"messages": [HumanMessage(question)]}, config)
        _print_turn(result["messages"][previous + 1 :])

    if args.once:
        ask(args.once)
        return

    print("AI Revenue Analyst — ask about performance, booking pace and rates ('exit' to leave)")
    while True:
        try:
            question = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        if question.lower() in {"exit", "quit"}:
            break
        ask(question)


if __name__ == "__main__":
    main()
