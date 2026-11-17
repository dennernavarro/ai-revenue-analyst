"""The backtest replays the review's routing rule on the seeded history."""

from datetime import date
from pathlib import Path

from revenue_analyst.backtest import run_backtest, score
from revenue_analyst.pms.mock import MockPMS

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def test_score_counts_confusion_matrix():
    rows = [
        {"rule": True, "actual_behind": True},  # tp
        {"rule": True, "actual_behind": False},  # fp
        {"rule": False, "actual_behind": True},  # fn
        {"rule": False, "actual_behind": False},  # tn
        {"rule": False, "actual_behind": False},  # tn
    ]
    s = score(rows, "rule")
    assert (s["tp"], s["fp"], s["fn"], s["tn"]) == (1, 1, 1, 2)
    assert s["precision"] == 0.5 and s["recall"] == 0.5 and s["accuracy"] == 0.6


def test_last_year_rule_beats_the_fixed_threshold_on_history():
    # Jan–Oct 2026: finished months whose last-year window is in the data.
    rows = run_backtest(MockPMS(DATA_DIR), date(2026, 1, 1), date(2026, 11, 1))
    assert len(rows) == 3 * 10 * 3  # properties × months × lead times

    last_year, fixed = score(rows, "last_year"), score(rows, "fixed_40")
    # The fixed 40% flags almost every window; the benchmark must be sharper.
    assert last_year["tp"] + last_year["fp"] < fixed["tp"] + fixed["fp"]
    assert last_year["precision"] > fixed["precision"]
    assert last_year["accuracy"] > fixed["accuracy"]
