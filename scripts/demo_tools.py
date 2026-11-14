"""Stage 1 checkpoint: inspect the toolbox exactly as an LLM will see it.

Still no LLM involved — this prints each tool's name, docstring and argument
schema (the model's entire view of your code), then invokes two of them.
"""

import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # allow running without installing the package

from revenue_analyst.datagen import AS_OF
from revenue_analyst.pms.mock import MockPMS
from revenue_analyst.tools import build_tools

if __name__ == "__main__":
    pms = MockPMS(ROOT / "data")
    tools = build_tools(pms, AS_OF)

    print("=== What the LLM sees ===")
    for t in tools:
        print(f"\n• {t.name}{tuple(t.args)}")
        print(textwrap.indent(t.description.strip(), "    "))

    print("\n=== Example invocations (as the LLM would make them) ===")
    by_name = {t.name: t for t in tools}
    print("\nlist_properties():")
    print(json.dumps(by_name["list_properties"].invoke({}), indent=2))

    args = {"property_id": "seaside-villa", "start_date": "2026-08-01", "end_date": "2026-09-01"}
    print(f"\nget_performance({args}):")
    print(json.dumps(by_name["get_performance"].invoke(args), indent=2))
