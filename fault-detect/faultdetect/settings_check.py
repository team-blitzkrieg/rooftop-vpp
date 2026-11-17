"""Rule (b): compare an inverter's protection settings with the CEB table.

The reference table is ``ceb_inverter_settings.json`` in the folder above.
The check only reads. It never writes a setting to an inverter.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REFERENCE_PATH = Path(__file__).resolve().parents[1] / "ceb_inverter_settings.json"

# Result words, worst first.
TRIPS_EARLY = "trips_too_early"  # leaves the grid during a dip: the Feb 2025 blackout problem
TOO_LOOSE = "too_loose"  # stays on, or reconnects, when it should not
DIFFERENT = "different"
NOT_READ = "not_read"
OK = "ok"


@dataclass(frozen=True)
class Finding:
    key: str
    result: str
    inverter_value: Any
    ceb_value: Any
    meaning: str

    @property
    def needs_review(self) -> bool:
        return self.result != OK


def load_reference(path: Path | str = REFERENCE_PATH) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _compare(kind: str, got: float, want: float, tol: float) -> str:
    if abs(got - want) <= tol:
        return OK
    higher = got > want
    if kind == "max":
        return TOO_LOOSE if higher else OK
    if kind == "min":
        return OK if higher else TOO_LOOSE
    if kind == "ride_through_low":  # trip level must not be above the CEB value
        return TRIPS_EARLY if higher else TOO_LOOSE
    if kind == "ride_through_high":  # trip level must not be below the CEB value
        return TOO_LOOSE if higher else TRIPS_EARLY
    if kind == "ride_through_time":  # clearing time must not be shorter
        return TOO_LOOSE if higher else TRIPS_EARLY
    return DIFFERENT


def check_settings(
    inverter: dict[str, Any],
    reference: dict | None = None,
    rel_tol: float = 0.01,
) -> list[Finding]:
    """Return one finding per CEB setting.

    ``inverter`` maps the keys of the reference table (for example ``uv1_pu``)
    to the values read from the inverter. A missing key gives ``not_read``,
    which also needs review: an unread setting is not a safe setting.
    """
    reference = reference or load_reference()
    findings: list[Finding] = []
    for key, spec in reference["settings"].items():
        want = spec["value"]
        got = inverter.get(key)
        if got is None:
            result = NOT_READ
        elif spec["kind"] == "bool":
            result = OK if bool(got) == bool(want) else TRIPS_EARLY
        else:
            result = _compare(spec["kind"], float(got), float(want), abs(want) * rel_tol)
        findings.append(Finding(key, result, got, want, spec["meaning"]))
    return findings


def summary(findings: list[Finding]) -> str:
    """The one-line status the homeowner sees."""
    return "Settings need review" if any(f.needs_review for f in findings) else "Settings OK"
