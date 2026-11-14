"""Stage 0 checkpoint: print a small performance report for every property.

No LLM involved — this is the deterministic layer the agents will later call.
"""

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # allow running without installing the package

from revenue_analyst.analytics import on_the_books_nights, performance_summary
from revenue_analyst.pms.mock import MockPMS

AUG = (date(2026, 8, 1), date(2026, 9, 1))
DEC = (date(2026, 12, 1), date(2027, 1, 1))

if __name__ == "__main__":
    pms = MockPMS(ROOT / "data")
    for prop in pms.list_properties():
        as_of = pms.as_of(prop.id)
        summary = performance_summary(prop, pms.get_reservations(prop.id, *AUG), *AUG)
        otb = on_the_books_nights(pms.get_reservations(prop.id, *DEC), as_of, *DEC)
        dec_capacity = prop.unit_count * 31

        print(f"\n{prop.name} ({prop.city}, {prop.unit_count} units)")
        print(
            f"  August 2026:  occupancy {summary.occupancy:6.1%}   "
            f"ADR ${summary.adr:7.2f}   RevPAR ${summary.revpar:7.2f}   "
            f"revenue ${summary.revenue:10,.2f}"
        )
        print(
            f"  December 2026 on the books (as of {as_of:%Y-%m-%d}): "
            f"{otb}/{dec_capacity} nights ({otb / dec_capacity:.0%})"
        )
