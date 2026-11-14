"""Regenerate the mock datasets in data/ (deterministic, safe to re-run)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # allow running without installing the package

from revenue_analyst.datagen import write_datasets

if __name__ == "__main__":
    for path in write_datasets(ROOT / "data"):
        size_kb = path.stat().st_size / 1024
        print(f"wrote {path.relative_to(ROOT)} ({size_kb:.0f} KB)")
