"""Test the under-performance rule on seeded faults. Simulated data only.

"Expected" output is the pvlib model driven by Open-Meteo archive weather.
"Actual" healthy output is the same model driven by NASA POWER weather, an
independent source. The two disagree from day to day, which stands in for the
gap between a weather service and a real roof. No measured inverter data is
used, because the project has none yet.

Run from the repository root:  python fault-detect/evaluate.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from faultdetect import flag_underperformance  # noqa: E402

RATED_KW = 5.0
YEAR = "2025"
FAULT_START = "2025-06-01"
LOCATIONS = ["colombo", "galle", "kandy", "anuradhapura", "jaffna"]


def load(source: str, location: str) -> pd.Series:
    path = ROOT / "data" / "processed" / "pv_simulated" / source / f"{location}.csv"
    frame = pd.read_csv(path, usecols=["timestamp", "system_kw", "pv_ac_kw_simulated"])
    frame = frame[frame["system_kw"] == RATED_KW]
    index = pd.to_datetime(frame["timestamp"]).dt.tz_localize(None).dt.floor("h")
    return pd.Series(frame["pv_ac_kw_simulated"].to_numpy(), index=index).loc[YEAR]


FAULTS = {
    "healthy": lambda kw: kw,
    "inverter_off": lambda kw: kw * 0.0,
    "half_the_panels_out": lambda kw: kw * 0.5,
    "export_stuck_at_40pct": lambda kw: kw.clip(upper=0.4 * RATED_KW),
    "soiling_15pct": lambda kw: kw * 0.85,
}


def evaluate(location: str) -> list[dict]:
    expected = load("open_meteo_archive", location)
    healthy = load("nasa_power", location).reindex(expected.index).fillna(0.0)
    rows = []
    for name, fault in FAULTS.items():
        actual = healthy.copy()
        if name != "healthy":
            actual.loc[FAULT_START:] = fault(actual.loc[FAULT_START:])
        days = flag_underperformance(
            pd.DataFrame({"actual_kw": actual, "expected_kw": expected}), RATED_KW
        )
        days.index = pd.to_datetime(days.index)
        before = days.loc[: pd.Timestamp(FAULT_START) - pd.Timedelta(days=1)]
        after = days.loc[FAULT_START:]
        first = after.index[after["alert"]].min() if after["alert"].any() else None
        rows.append(
            {
                "location": location,
                "case": name,
                "judged_days": int(days["judged"].sum()),
                "alert_days_while_healthy": int(
                    (days if name == "healthy" else before)["alert"].sum()
                ),
                "detected": first is not None if name != "healthy" else None,
                "days_to_first_alert": (first - pd.Timestamp(FAULT_START)).days + 1
                if first is not None and name != "healthy"
                else None,
            }
        )
    return rows


def main() -> None:
    rows = [row for location in LOCATIONS for row in evaluate(location)]
    table = pd.DataFrame(rows)
    out = Path(__file__).resolve().parent / "results"
    out.mkdir(exist_ok=True)
    table.to_csv(out / "seeded_fault_test.csv", index=False)
    meta = {
        "is_simulated": True,
        "is_measured_generation": False,
        "year": YEAR,
        "fault_start": FAULT_START,
        "system_kw": RATED_KW,
        "expected_from": "pvlib model on Open-Meteo archive weather",
        "healthy_actual_from": "pvlib model on NASA POWER weather",
        "script": "fault-detect/evaluate.py",
    }
    (out / "seeded_fault_test.meta.json").write_text(json.dumps(meta, indent=2))
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
