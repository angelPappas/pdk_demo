"""PDK constants, read from constants.csv (single source of truth)."""

import csv
from pathlib import Path

_CSV = Path(__file__).with_name("constants.csv")


def _load() -> dict[str, float]:
    with _CSV.open(newline="") as f:
        return {row["name"]: float(row["value"]) for row in csv.DictReader(f)}


CONSTANTS = _load()