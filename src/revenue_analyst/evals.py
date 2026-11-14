"""Stage 8: evaluation — regression tests for agent BEHAVIOR.

    uv run python -m revenue_analyst.evals            # local run + report
    uv run python -m revenue_analyst.evals --langsmith  # also log a LangSmith experiment

Three ideas:

1. **Ground truth is computed, not hand-written.** Every expected number comes
   from the same deterministic analytics the tools use, over the same seeded
   data — so the dataset can never drift out of sync with the simulator.
2. **Evaluators check behavior, not prose**: are the key numbers in the reply
   (within tolerance)? were the right tools called? did "full month" questions
   use half-open windows correctly (the bug we caught live in Stage 2)?
3. **LangSmith is optional.** Everything runs and scores locally; with
   LANGSMITH_API_KEY set, the same dataset and evaluators also produce a
   tracked experiment you can inspect run by run.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from datetime import date

from langchain_core.messages import AIMessage, HumanMessage

from revenue_analyst.analytics import booking_pace, performance_summary
from revenue_analyst.llm import message_text
from revenue_analyst.pms.mock import MockPMS
from revenue_analyst.pms.provider import PMSProvider

AUG = (date(2026, 8, 1), date(2026, 9, 1))
DEC = (date(2026, 12, 1), date(2027, 1, 1))


@dataclass
class Example:
    question: str
    expected_tools: set[str] = field(default_factory=set)
    numbers: list[tuple[float, float]] = field(default_factory=list)
    """(expected value, tolerance) pairs that must appear in the reply."""
    text_all: list[str] = field(default_factory=list)
    text_any: list[str] = field(default_factory=list)
    check_full_month_windows: bool = False


def build_dataset(pms: PMSProvider, as_of) -> list[Example]:
    props = {p.id: p for p in pms.list_properties()}
    summaries = {
        pid: performance_summary(p, pms.get_reservations(pid, *AUG), *AUG)
        for pid, p in props.items()
    }
    paces = {
        pid: booking_pace(p, pms.get_reservations(pid, *DEC), as_of, *DEC)
        for pid, p in props.items()
    }
    best_revpar = max(summaries.values(), key=lambda s: s.revpar)

    examples = [
        Example(
            question=f"How was {props[pid].name} in August 2026? Give occupancy and ADR.",
            expected_tools={"get_performance"},
            numbers=[(summaries[pid].occupancy * 100, 0.15), (summaries[pid].adr, 0.75)],
        )
        for pid in props
    ]
    examples += [
        Example(
            question="Which property had the highest RevPAR in August 2026?",
            expected_tools={"get_performance"},
            text_all=[props[best_revpar.property_id].name],
        ),
        Example(
            question=(
                "How many nights are already on the books for the full month of "
                "December 2026 at Mountain Cabins?"
            ),
            expected_tools={"get_booking_pace"},
            numbers=[(paces["mountain-cabins"].pace[0].nights_on_the_books, 0.01)],
            check_full_month_windows=True,
        ),
        Example(
            question=(
                "What is the total night capacity of Urban Boutique for the full "
                "month of December 2026, and how much of it is sold?"
            ),
            expected_tools={"get_booking_pace"},
            numbers=[(paces["urban-boutique"].capacity_nights, 0.01)],
            check_full_month_windows=True,
        ),
        Example(
            question="How many units does Mountain Cabins have?",
            expected_tools={"list_properties"},
            numbers=[(props["mountain-cabins"].unit_count, 0.01)],
        ),
        Example(
            question="How did Hotel Copacabana perform in August 2026?",
            text_any=[p.name for p in props.values()] + ["not", "no property", "unknown"],
        ),
        Example(
            question="What will the occupancy be in February 2027 at Seaside Villa?",
            text_any=["book", "so far", "cannot", "predict", "current"],
        ),
    ]
    return examples


# --- scoring ----------------------------------------------------------------

_NUMBER = re.compile(r"-?\d[\d,]*\.?\d*")


def extract_numbers(text: str) -> list[float]:
    values = []
    for raw in _NUMBER.findall(text):
        try:
            values.append(float(raw.replace(",", "")))
        except ValueError:
            continue
    return values


def has_number(reply: str, value: float, tol: float) -> bool:
    return any(abs(found - value) <= tol for found in extract_numbers(reply))


def full_month_windows_ok(tool_calls: list[dict]) -> bool:
    """Half-open convention: a window starting on the 1st and spanning ~a month
    must END on the 1st of the next month, not on the 28th-31st."""
    for call in tool_calls:
        args = call.get("args", {})
        try:
            start = date.fromisoformat(str(args["start_date"]))
            end = date.fromisoformat(str(args["end_date"]))
        except (KeyError, ValueError):
            continue
        if start.day == 1 and 27 <= (end - start).days <= 32 and end.day != 1:
            return False
    return True


def score(example: Example, reply: str, tool_calls: list[dict]) -> dict[str, bool]:
    called = {call["name"] for call in tool_calls}
    reply_lower = reply.lower()
    checks = {}
    if example.expected_tools:
        checks["tools"] = example.expected_tools <= called
    if example.numbers:
        checks["numbers"] = all(has_number(reply, v, tol) for v, tol in example.numbers)
    if example.text_all:
        checks["text"] = all(t.lower() in reply_lower for t in example.text_all)
    if example.text_any:
        checks["text_any"] = any(t.lower() in reply_lower for t in example.text_any)
    if example.check_full_month_windows:
        checks["windows"] = full_month_windows_ok(tool_calls)
    return checks


# --- runner -----------------------------------------------------------------


def run_example(agent, question: str) -> tuple[str, list[dict]]:
    result = agent.invoke({"messages": [HumanMessage(question)]})
    messages = result["messages"]
    tool_calls = [
        call for m in messages if isinstance(m, AIMessage) for call in m.tool_calls
    ]
    return message_text(messages[-1]), tool_calls


def main() -> None:
    from dotenv import load_dotenv

    from revenue_analyst.agents.v1_react import build_agent
    from revenue_analyst.config import Settings

    load_dotenv()
    parser = argparse.ArgumentParser(description="Evaluate the revenue analyst agent")
    parser.add_argument("--langsmith", action="store_true", help="also log a LangSmith experiment")
    parser.add_argument("--limit", type=int, help="run only the first N examples")
    args = parser.parse_args()

    settings = Settings()
    pms = MockPMS(settings.data_dir)
    as_of = pms.as_of(pms.list_properties()[0].id)
    dataset = build_dataset(pms, as_of)[: args.limit]
    agent = build_agent(pms, as_of, model=settings.model)

    results = []
    for i, example in enumerate(dataset, 1):
        reply, tool_calls = run_example(agent, example.question)
        checks = score(example, reply, tool_calls)
        passed = all(checks.values())
        results.append(passed)
        failed = [name for name, ok in checks.items() if not ok]
        status = "PASS" if passed else f"FAIL ({', '.join(failed)})"
        print(f"{i:2d}. [{status:>22s}] {example.question[:70]}")

    total, ok = len(results), sum(results)
    print(f"\n{ok}/{total} passed ({ok / total:.0%}) — model: {settings.model}")

    if args.langsmith:
        _run_langsmith_experiment(agent, dataset, settings.model)


def _run_langsmith_experiment(agent, dataset: list[Example], model: str) -> None:
    """Upload the dataset and run a tracked experiment (needs LANGSMITH_API_KEY)."""
    from langsmith import Client, evaluate

    client = Client()
    name = "ai-revenue-analyst-behavior"
    if not client.has_dataset(dataset_name=name):
        ls_dataset = client.create_dataset(dataset_name=name)
        client.create_examples(
            dataset_id=ls_dataset.id,
            inputs=[{"question": e.question} for e in dataset],
            outputs=[
                {
                    "expected_tools": sorted(e.expected_tools),
                    "numbers": e.numbers,
                    "text_all": e.text_all,
                    "text_any": e.text_any,
                    "check_full_month_windows": e.check_full_month_windows,
                }
                for e in dataset
            ],
        )

    def target(inputs: dict) -> dict:
        reply, tool_calls = run_example(agent, inputs["question"])
        return {"reply": reply, "tool_calls": tool_calls}

    def behavior(inputs: dict, outputs: dict, reference_outputs: dict) -> bool:
        example = Example(
            question=inputs["question"],
            expected_tools=set(reference_outputs.get("expected_tools", [])),
            numbers=[tuple(n) for n in reference_outputs.get("numbers", [])],
            text_all=reference_outputs.get("text_all", []),
            text_any=reference_outputs.get("text_any", []),
            check_full_month_windows=reference_outputs.get("check_full_month_windows", False),
        )
        return all(score(example, outputs["reply"], outputs["tool_calls"]).values())

    result = evaluate(
        target,
        data=name,
        evaluators=[behavior],
        experiment_prefix=model.replace(":", "-").replace("/", "-"),
    )
    print(f"LangSmith experiment: {result.experiment_name}")


if __name__ == "__main__":
    main()
