#!/usr/bin/env python3
"""Export PV forecast artefacts under docs/data for GitHub Pages (static JSON)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dashboard import artifacts  # noqa: E402
from forecasting.config import MODEL_DIR, REPO_ROOT  # noqa: E402

DOCS_DATA = REPO_ROOT / "docs" / "data"
TRAIN_CMD = [
    sys.executable,
    "-m",
    "forecasting",
    "train",
    "--synthetic",
    "--start",
    "2024-06-01",
    "--end",
    "2024-06-21",
    "--estimators",
    "80",
]


def _jsonable(value: object) -> object:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)


def _test_mae(exp: dict) -> tuple[float | None, float | None]:
    try:
        overall = exp["metrics"]["test"]["overall"]
        return overall["lightgbm"]["mae_kw"], overall["baseline"]["mae_kw"]
    except (KeyError, TypeError):
        return None, None


def _forecast_rows_to_json(df: pd.DataFrame) -> list[dict]:
    work = df.copy()
    for col in ("timestamp", "issued_at"):
        if col in work.columns:
            work[col] = pd.to_datetime(work[col], utc=True).map(
                lambda t: t.isoformat() if pd.notna(t) else None
            )
    records = work.to_dict(orient="records")
    return [_jsonable(r) for r in records]


def _clear_generated_data() -> None:
    if DOCS_DATA.is_dir():
        import shutil

        shutil.rmtree(DOCS_DATA)
    DOCS_DATA.mkdir(parents=True, exist_ok=True)
    (DOCS_DATA / "experiments").mkdir(parents=True, exist_ok=True)
    (DOCS_DATA / "forecasts").mkdir(parents=True, exist_ok=True)


def export_pages_data() -> dict:
    models = artifacts.list_model_dirs()
    if not models:
        raise SystemExit(
            "No trained LightGBM model found under forecasting/models/ "
            "(pv-lgbm-*). Train first or use --with-demo-train."
        )

    _clear_generated_data()

    sites_df = artifacts.list_sites()
    sites: list[dict] = []
    if not sites_df.empty:
        sites = sites_df.to_dict(orient="records")

    versions = [artifacts.model_version_from_dir(m) for m in models]
    forecast_index: dict[str, dict[str, list[str]]] = {}
    forecast_counts: dict[str, int] = {}
    experiment_md: dict[str, str | None] = {}

    for model_dir in models:
        version = artifacts.model_version_from_dir(model_dir)
        exp = artifacts.load_experiment(model_dir)
        if not exp:
            print(f"warning: skipping {version}: missing experiment.json", file=sys.stderr)
            continue

        out_exp = DOCS_DATA / "experiments" / f"{version}.json"
        out_exp.write_text(json.dumps(exp, indent=2) + "\n", encoding="utf-8")

        md = artifacts.load_experiment_markdown(model_dir)
        if md:
            experiment_md[version] = md
            (DOCS_DATA / "experiments" / f"{version}.md").write_text(md, encoding="utf-8")

        site_days: dict[str, list[str]] = {}
        for site_id in sites_df["site_id"].astype(str) if not sites_df.empty else []:
            days = artifacts.list_forecast_days(version, site_id)
            if days:
                site_days[site_id] = days
                for day in days:
                    csv_df = artifacts.read_forecast_csv(version, site_id, day)
                    if csv_df is None or csv_df.empty:
                        continue
                    rel_dir = DOCS_DATA / "forecasts" / version / site_id
                    rel_dir.mkdir(parents=True, exist_ok=True)
                    out_path = rel_dir / f"{day}.json"
                    payload = _forecast_rows_to_json(csv_df)
                    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        forecast_index[version] = site_days
        forecast_counts[version] = artifacts.count_forecast_files(version)

    latest = models[0]
    latest_exp = artifacts.load_experiment(latest)
    lgb_mae, base_mae = _test_mae(latest_exp or {})
    latest_version = artifacts.model_version_from_dir(latest)

    manifest = {
        "project": "Rooftops to Power Plant",
        "generated_for": "github_pages",
        "repo_root_note": "Paths in experiment JSON may point at local training dirs; static UI uses docs/data only.",
        "timezone": "Asia/Colombo",
        "data_label": (latest_exp or {}).get("data_label", "SIMULATED"),
        "controls_equipment": False,
        "disclaimer": (
            "SIMULATED data for the Sri Lanka pilot. Issue time is midnight Asia/Colombo. "
            "Forecasts are for scheduling visibility only — not inverter control."
        ),
        "sites": sites,
        "model_versions": versions,
        "latest_model_version": latest_version,
        "overview": {
            "test_mae_lightgbm_kw": lgb_mae,
            "test_mae_baseline_kw": base_mae,
            "lightgbm_beats_baseline_on_test_mae": (latest_exp or {}).get(
                "lightgbm_beats_baseline_on_test_mae"
            ),
            "forecast_csv_files": forecast_counts.get(latest_version, 0),
        },
        "forecast_days_by_version": forecast_index,
        "forecast_file_counts": forecast_counts,
        "experiment_markdown_available": {
            v: bool(experiment_md.get(v)) for v in versions
        },
    }

    manifest_path = DOCS_DATA / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-demo-train",
        action="store_true",
        help="Run a short synthetic train before export (same command as the Streamlit dashboard).",
    )
    args = parser.parse_args()

    if args.with_demo_train:
        print("Running short synthetic train…", flush=True)
        proc = subprocess.run(TRAIN_CMD, cwd=REPO_ROOT)
        if proc.returncode != 0:
            raise SystemExit(f"Training failed with exit code {proc.returncode}")

    if not MODEL_DIR.is_dir() or not artifacts.list_model_dirs():
        raise SystemExit(
            "No trained LightGBM model found under forecasting/models/ "
            "(pv-lgbm-*). Train first or use --with-demo-train."
        )

    manifest = export_pages_data()
    print(json.dumps({"manifest": manifest["overview"], "versions": len(manifest["model_versions"])}, indent=2))
    print(f"Wrote static data under {DOCS_DATA.relative_to(REPO_ROOT)}/", flush=True)


if __name__ == "__main__":
    main()