"""Copy a small Colombo month, and one live snapshot, into data/sample.

The full files stay under data/raw and data/processed, which git ignores.
The sample is the committed extract teammates and judges can open.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from data.pipeline.config import REPO_ROOT
from data.pipeline.tables import read_weather_csv, slice_month, write_dataset

# Forecast-input and observed series a judge should be able to tell apart.
REQUIRED_WEATHER = (
    "open_meteo_archive",
    "nasa_power",
    "open_meteo_previous_day1",
)
OPTIONAL_WEATHER = ("open_meteo_historical_forecast",)
PV_SOURCE_FOR_SAMPLE = "open_meteo_archive"


def export_month(
    *,
    month: str,
    location_id: str,
    weather_root: Path,
    pv_root: Path,
    sample_dir: Path,
) -> list[Path]:
    written: list[Path] = []
    missing: list[str] = []
    for source_id in REQUIRED_WEATHER:
        path = weather_root / source_id / f"{location_id}.csv"
        if not path.is_file():
            missing.append(str(path))
            continue
        written.append(
            _write_month_slice(
                path,
                month=month,
                location_id=location_id,
                sample_dir=sample_dir,
                filename=f"{location_id}_{source_id}_{month}.csv",
            )
        )
    if missing:
        raise FileNotFoundError(
            "Missing weather files. Fetch them first.\n" + "\n".join(missing)
        )

    for source_id in OPTIONAL_WEATHER:
        path = weather_root / source_id / f"{location_id}.csv"
        if not path.is_file():
            print(f"No {source_id} file at {path}; sample will not include it.")
            continue
        written.append(
            _write_month_slice(
                path,
                month=month,
                location_id=location_id,
                sample_dir=sample_dir,
                filename=f"{location_id}_{source_id}_{month}.csv",
            )
        )

    pv_path = pv_root / PV_SOURCE_FOR_SAMPLE / f"{location_id}.csv"
    if not pv_path.is_file():
        raise FileNotFoundError(
            f"Missing simulated PV file {pv_path}. Run simulate-pv on the "
            f"{PV_SOURCE_FOR_SAMPLE} weather first."
        )
    written.append(
        _write_month_slice(
            pv_path,
            month=month,
            location_id=location_id,
            sample_dir=sample_dir,
            filename=f"{location_id}_pv_simulated_{PV_SOURCE_FOR_SAMPLE}_{month}.csv",
        )
    )
    return written


def export_live_snapshot(
    *,
    location_id: str,
    live_root: Path,
    sample_dir: Path,
) -> list[Path]:
    location_dir = live_root / location_id
    if not location_dir.is_dir():
        raise FileNotFoundError(
            f"No live snapshots in {location_dir}. Run fetch-live first."
        )
    snapshots = sorted(path for path in location_dir.iterdir() if path.is_dir())
    if not snapshots:
        raise FileNotFoundError(f"No live snapshots in {location_dir}.")
    latest = snapshots[-1]
    sample_dir.mkdir(parents=True, exist_ok=True)
    name_map = {
        "current.csv": f"{location_id}_live_current.csv",
        "hourly.csv": f"{location_id}_live_hourly.csv",
        "minutely_15.csv": f"{location_id}_live_minutely_15.csv",
        "pv_hourly_simulated.csv": f"{location_id}_live_pv_hourly_simulated.csv",
        "pv_minutely_15_simulated.csv": f"{location_id}_live_pv_minutely_15_simulated.csv",
    }
    written: list[Path] = []
    for source_name, sample_name in name_map.items():
        source = latest / source_name
        if not source.is_file():
            if source_name in {"current.csv", "hourly.csv"}:
                raise FileNotFoundError(f"Live snapshot {latest} has no {source_name}")
            continue
        target = sample_dir / sample_name
        shutil.copyfile(source, target)
        written.append(target)
        meta_source = source.with_suffix(".meta.json")
        if meta_source.is_file():
            meta = json.loads(meta_source.read_text(encoding="utf-8"))
        else:
            meta = {}
        meta["sample"] = True
        meta["sample_of"] = _repo_relative(source)
        meta["note_sample"] = (
            "Committed copy of one live forecast pull. The timestamped "
            "original under data/raw/live is gitignored."
        )
        target.with_suffix(".meta.json").write_text(
            json.dumps(meta, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        written.append(target.with_suffix(".meta.json"))

    snapshot_meta = latest / "meta.json"
    if snapshot_meta.is_file():
        meta = json.loads(snapshot_meta.read_text(encoding="utf-8"))
        meta["sample"] = True
        meta["sample_of"] = _repo_relative(latest)
        meta["note"] = (
            "Index for one live pull. current, hourly and minutely_15 are "
            "forecast weather. Files named pv_*_simulated are pvlib output, "
            "not measured generation; their own metadata has pv_is_simulated true."
        )
        target = sample_dir / f"{location_id}_live.meta.json"
        target.write_text(json.dumps(meta, indent=2, default=str) + "\n", encoding="utf-8")
        written.append(target)
    return written


def _repo_relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def _write_month_slice(
    path: Path,
    *,
    month: str,
    location_id: str,
    sample_dir: Path,
    filename: str,
) -> Path:
    frame = read_weather_csv(path)
    # PV files use the same timestamp column. read_weather_csv keeps every
    # other column, which is what we want for both weather and PV tables.
    sliced = slice_month(frame, location_id, month)
    if sliced.empty:
        span = ""
        if len(frame):
            span = (
                f" File spans {frame['timestamp'].min()} to {frame['timestamp'].max()}."
            )
        raise ValueError(f"No {location_id} rows for {month} in {path}.{span}")

    meta_path = path.with_suffix(".meta.json")
    if meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    else:
        meta = {}
    meta["sample"] = True
    meta["sample_month"] = month
    meta["sample_location_id"] = location_id
    meta["sample_rows"] = int(len(sliced))
    meta["rows"] = int(len(sliced))
    meta["sample_of"] = _repo_relative(path)
    meta["note_sample"] = (
        "Small committed extract of one calendar month. Same columns as the "
        "full file, which is gitignored under data/raw or data/processed. "
        "start_date and end_date, when present, are the range of that full download."
    )
    target = sample_dir / filename
    write_dataset(sliced, target, meta)
    print(f"Wrote sample {target} ({len(sliced)} rows)")
    return target
