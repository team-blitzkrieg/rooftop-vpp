"""Scheduled fault check. It reads stored rows and never writes a setpoint.

    python -m api.fault_job

Readings are compared with the PV forecast baseline for the same hour.
Inverter registers are not read, so the settings rule stays not_read.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fault-detect"))

from faultdetect.underperformance import flag_underperformance  # noqa: E402


def main() -> int:
    if not os.environ.get("DATABASE_URL", "").strip():
        print("DATABASE_URL is not set. Skipping.")
        return 0
    from api.postgres import PostgresStore

    summary = run_fault_check(PostgresStore(os.environ["DATABASE_URL"]))
    print(
        f"Fault check for {summary['sites']} sites. "
        "Settings stay not_read. No inverter was changed."
    )
    return 0


def run_fault_check(store, *, now=None) -> dict:
    moment = now or datetime.now(timezone.utc)
    written = []
    for site in store.list_sites():
        site_id = site["site_id"]
        for result in evaluate_site(store, site, moment):
            store.save_fault(
                site_id,
                result["rule"],
                result["status"],
                detail=result["detail"],
                data_label=result["data_label"],
                is_simulated=result["is_simulated"],
                checked_at=moment,
            )
            written.append({"site_id": site_id, **result})
    return {"sites": len({row["site_id"] for row in written}), "results": written}


def evaluate_site(store, site: dict, moment: datetime) -> list[dict]:
    settings = {
        "rule": "settings",
        "status": "not_read",
        "detail": "Inverter registers have not been read. This is not a pass.",
        "data_label": "NOT_AVAILABLE",
        "is_simulated": False,
    }
    site_id = site["site_id"]
    readings = [
        row
        for row in store.readings_for(site_id, include_simulated=True)
        if row.get("pv_kw") is not None
    ]
    forecast = store.latest_success(site_id, "pv")
    if len(readings) < 24 or forecast is None or not forecast.get("rows"):
        return [
            settings,
            {
                "rule": "underperformance",
                "status": "insufficient",
                "detail": "Need PV readings and a PV forecast baseline before this rule can run.",
                "data_label": "NOT_AVAILABLE",
                "is_simulated": False,
            },
        ]
    expected = {}
    for row in forecast["rows"]:
        stamp = pd.Timestamp(row["timestamp"])
        if stamp.tzinfo is None:
            stamp = stamp.tz_localize("UTC")
        expected[stamp.tz_convert("UTC").floor("h")] = row.get("baseline_kw")
    actual_rows = []
    simulated = False
    for row in readings:
        stamp = pd.Timestamp(row["timestamp"])
        if stamp.tzinfo is None:
            stamp = stamp.tz_localize("UTC")
        hour = stamp.tz_convert("UTC").floor("h")
        baseline = expected.get(hour)
        if baseline is None:
            continue
        simulated = simulated or bool(row.get("is_simulated"))
        actual_rows.append({"timestamp": hour, "actual_kw": float(row["pv_kw"]), "expected_kw": float(baseline)})
    if len(actual_rows) < 24:
        return [
            settings,
            {
                "rule": "underperformance",
                "status": "insufficient",
                "detail": "Readings and the forecast baseline do not share enough hours.",
                "data_label": "SIMULATED" if simulated else "MEASURED",
                "is_simulated": simulated,
            },
        ]
    frame = pd.DataFrame(actual_rows).drop_duplicates("timestamp").set_index("timestamp").sort_index()
    rated = float(site.get("system_kw") or 0) or 1.0
    days = flag_underperformance(frame, rated)
    alert = bool(days["alert"].any()) if len(days) else False
    label = "SIMULATED" if simulated else "MEASURED"
    detail = (
        "Three sunny days in a row are below 60% of the forecast baseline."
        if alert
        else "No three-day underperformance against the forecast baseline."
    )
    if simulated:
        detail += " The readings are simulated."
    return [
        settings,
        {
            "rule": "underperformance",
            "status": "alert" if alert else "ok",
            "detail": detail,
            "data_label": label,
            "is_simulated": simulated,
        },
    ]


if __name__ == "__main__":
    raise SystemExit(main())
