"""Train the normalised LightGBM model, score it, and write a versioned forecast.

The saved target is AC kW, clipped to the nameplate and set to zero when the
sun is down. Training itself fits pv_kw / system_kw so one model covers every
home. Artefacts go in a version directory. They are not a command to equipment.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from forecasting.baseline import baseline_power, library_versions
from forecasting.config import (
    BASELINE_LOSS_FACTOR,
    DEFAULT_EARLY_STOPPING,
    DEFAULT_LGBM_PARAMS,
    DEFAULT_N_ESTIMATORS,
    FEATURE_COLUMNS,
    REPO_ROOT,
    TIMEZONE,
    WEATHER_COLUMNS,
)
from forecasting.features import assert_no_target_leakage, infer_resolution
from forecasting.metrics import score, slice_masks
from forecasting.split import assert_chronological, issue_bounds, split_by_issue
from forecasting.tables import write_table


def train_and_evaluate(
    frame: pd.DataFrame,
    *,
    model_dir: Path,
    forecast_dir: Path,
    resolution: str | None = None,
    n_estimators: int = DEFAULT_N_ESTIMATORS,
    early_stopping: int = DEFAULT_EARLY_STOPPING,
    params: dict | None = None,
    loss_factor: float = BASELINE_LOSS_FACTOR,
    seed: int = 7,
) -> dict:
    assert_no_target_leakage(frame)
    found = infer_resolution(frame)
    if resolution is None:
        resolution = found
    elif resolution != found:
        raise ValueError(f"Asked for {resolution}, timestamps look like {found}")

    usable, dropped = _drop_incomplete(frame)
    usable = usable.copy()
    usable["baseline_kw"] = baseline_power(usable, loss_factor).to_numpy()
    split = split_by_issue(usable)
    assert_chronological(split)

    lgb_params = dict(DEFAULT_LGBM_PARAMS)
    if params:
        lgb_params.update(params)
    lgb_params["seed"] = int(seed)
    lgb_params["num_threads"] = 1

    train_y = _target(split.train)
    val_y = _target(split.val)
    train_set = lgb.Dataset(
        split.train[FEATURE_COLUMNS],
        label=train_y,
        feature_name=list(FEATURE_COLUMNS),
        free_raw_data=False,
    )
    val_set = lgb.Dataset(
        split.val[FEATURE_COLUMNS],
        label=val_y,
        reference=train_set,
        feature_name=list(FEATURE_COLUMNS),
        free_raw_data=False,
    )
    booster = lgb.train(
        lgb_params,
        train_set,
        num_boost_round=int(n_estimators),
        valid_sets=[val_set],
        valid_names=["val"],
        callbacks=[
            lgb.early_stopping(int(early_stopping), verbose=False),
            lgb.log_evaluation(period=0),
        ],
    )

    version = "pv-lgbm-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    artifact = Path(model_dir) / version
    artifact.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(artifact / "model.txt"))
    (artifact / "features.json").write_text(
        json.dumps(list(FEATURE_COLUMNS), indent=2) + "\n",
        encoding="utf-8",
    )

    predicted = {
        "train": predict_kw(booster, split.train),
        "val": predict_kw(booster, split.val),
        "test": predict_kw(booster, split.test),
    }
    metrics = {
        name: _score_part(getattr(split, name), predicted[name])
        for name in ("train", "val", "test")
    }
    beats = _beats(metrics["test"]["overall"])
    data_label = "SIMULATED" if bool(usable["is_simulated"].any()) else "MEASURED"
    record = {
        "project": "Rooftops to Power Plant",
        "model_version": version,
        "git_sha": git_sha(),
        "data_label": data_label,
        "controls_equipment": False,
        "timezone": TIMEZONE,
        "target": "pv_kw / system_kw during training; saved forecasts are AC kW",
        "baseline": {
            "name": "poa_times_system_kw_times_loss",
            "loss_factor": float(loss_factor),
            "loss_factor_fitted": False,
            "library": "pvlib",
            "transposition": "isotropic",
        },
        "data_window": {
            "start": usable["timestamp"].min().isoformat(),
            "end": usable["timestamp"].max().isoformat(),
            "n_rows": int(len(usable)),
            "rows_dropped_missing_weather": int(dropped),
            "n_sites": int(usable["site_id"].nunique()),
            "sites": [str(item) for item in sorted(usable["site_id"].unique())],
            "resolution": resolution,
        },
        "split": {
            "rule": (
                "Issue days stay whole. They are ordered in time and not shuffled. "
                "The last training day is before the first validation day, and the "
                "last validation day is before the first test day."
            ),
            "train_fraction": 0.70,
            "val_fraction": 0.15,
            "train": issue_bounds(split.train),
            "val": issue_bounds(split.val),
            "test": issue_bounds(split.test),
        },
        "features": list(FEATURE_COLUMNS),
        "params": {key: _jsonable(value) for key, value in lgb_params.items()},
        "n_estimators_requested": int(n_estimators),
        "best_iteration": int(booster.best_iteration or 0),
        "early_stopping_rounds": int(early_stopping),
        "metrics": metrics,
        "nmae_definition": "MAE in kW divided by the mean system_kw on the same rows",
        "cloudy_definition": (
            "Daylight hours (solar elevation > 0) on issue-days whose daylight "
            "forecast cloud cover averages at least 60 percent."
        ),
        "midday_definition": "Local hours 11, 12 and 13 in Asia/Colombo",
        "lightgbm_beats_baseline_on_test_mae": beats,
        "verdict": verdict(beats, metrics["test"]),
        "library_versions": {**library_versions(), "lightgbm": lgb.__version__},
        "note": (
            "SIMULATED means the target was generated, not read from an inverter. "
            "A lower error on that series is not a result about the pilot homes. "
            "This run did not send a setpoint to any device."
        ),
    }
    (artifact / "experiment.json").write_text(
        json.dumps(record, indent=2) + "\n",
        encoding="utf-8",
    )
    (artifact / "experiment.md").write_text(render_markdown(record), encoding="utf-8")
    forecast_root = write_forecasts(
        split.test,
        predicted["test"],
        version=version,
        forecast_dir=Path(forecast_dir),
        resolution=resolution,
    )
    record["paths"] = {
        "model": str(artifact / "model.txt"),
        "experiment": str(artifact / "experiment.json"),
        "forecasts": str(forecast_root),
    }
    return record


def predict_kw(booster: lgb.Booster, frame: pd.DataFrame) -> np.ndarray:
    raw = np.asarray(booster.predict(frame[FEATURE_COLUMNS]), dtype=float)
    norm = np.clip(raw, 0.0, 1.0)
    kw = norm * frame["system_kw"].to_numpy(dtype=float)
    night = frame["solar_elevation_deg"].to_numpy(dtype=float) <= 0.0
    kw = np.where(night, 0.0, kw)
    return np.round(np.clip(kw, 0.0, frame["system_kw"].to_numpy(dtype=float)), 4)


def write_forecasts(
    part: pd.DataFrame,
    predicted: np.ndarray,
    *,
    version: str,
    forecast_dir: Path,
    resolution: str,
) -> Path:
    table = part.loc[
        :,
        [
            "site_id",
            "timestamp",
            "issued_at",
            "baseline_kw",
            "system_kw",
            "data_label",
            "is_simulated",
        ],
    ].copy()
    table["site_id"] = table["site_id"].astype(str)
    table["lead_hours"] = (table["timestamp"] - table["issued_at"]).dt.total_seconds() / 3600.0
    table["pv_kw"] = np.asarray(predicted, dtype=float)
    table["baseline_kw"] = table["baseline_kw"].astype(float)
    table["model_version"] = version
    table["resolution"] = resolution
    table = table[
        [
            "site_id",
            "timestamp",
            "issued_at",
            "lead_hours",
            "pv_kw",
            "baseline_kw",
            "system_kw",
            "model_version",
            "resolution",
            "data_label",
            "is_simulated",
        ]
    ]
    if (table["pv_kw"] < -1e-6).any() or (table["pv_kw"] - table["system_kw"] > 1e-6).any():
        raise ValueError("A forecast fell outside 0 to system_kw")
    if (table["baseline_kw"] < -1e-6).any() or (
        table["baseline_kw"] - table["system_kw"] > 1e-6
    ).any():
        raise ValueError("The baseline fell outside 0 to system_kw")
    root = Path(forecast_dir) / version
    for (site_id, issued), group in table.groupby(["site_id", "issued_at"], sort=True):
        issued_at = pd.Timestamp(issued)
        if issued_at.tzinfo is None:
            issued_at = issued_at.tz_localize(TIMEZONE)
        else:
            issued_at = issued_at.tz_convert(TIMEZONE)
        day = issued_at.strftime("%Y-%m-%d")
        simulated = bool(group["is_simulated"].any())
        write_table(
            group,
            root / str(site_id) / f"{day}.csv",
            {
                "project": "Rooftops to Power Plant",
                "model_version": version,
                "site_id": str(site_id),
                "issued_at": issued_at.isoformat(),
                "resolution": resolution,
                "timezone": TIMEZONE,
                "data_label": "SIMULATED" if simulated else "MEASURED",
                "is_simulated": simulated,
                "controls_equipment": False,
                "rows": int(len(group)),
                "note": (
                    "pv_kw is the LightGBM AC forecast. baseline_kw is the physics "
                    "baseline. The scheduler may read this file. Nothing here is sent "
                    "to an inverter. SIMULATED is not a pilot measurement."
                ),
            },
        )
    return root


def format_report(record: dict) -> str:
    lines = [f"Data: {record['data_label']}."]
    if record["data_label"] == "SIMULATED":
        lines.append("These figures are not measurements from a pilot inverter.")
    lines.append("This command does not control any equipment.")
    lines.append("nMAE is MAE divided by the mean system size on the same rows.")
    lines.append("")
    for slice_name in ("overall", "cloudy", "midday"):
        block = record["metrics"]["test"][slice_name]
        lines.append(f"test {slice_name:8} baseline  {_fmt(block['baseline'])}")
        lines.append(f"test {slice_name:8} lightgbm  {_fmt(block['lightgbm'])}")
    lines.append("")
    lines.append(record["verdict"])
    lines.append(f"Model version: {record['model_version']}")
    lines.append(f"Git sha: {record['git_sha']}")
    if "paths" in record:
        lines.append(f"Experiment: {record['paths']['experiment']}")
        lines.append(f"Forecasts: {record['paths']['forecasts']}")
    return "\n".join(lines) + "\n"


def render_markdown(record: dict) -> str:
    window = record["data_window"]
    split = record["split"]
    lines = [
        f"# PV forecast {record['model_version']}",
        "",
        f"Data: {record['data_label']}.",
        "",
        record["note"],
        "",
        "## Window",
        "",
        f"- Time zone: {record['timezone']}",
        f"- Resolution: {window['resolution']}",
        f"- From {window['start']} to {window['end']}",
        f"- {window['n_rows']} rows, {window['n_sites']} sites: {', '.join(window['sites'])}",
        f"- Rows dropped for missing weather: {window['rows_dropped_missing_weather']}",
        "",
        "## Split",
        "",
        split["rule"],
        "",
        f"- Train: {split['train']['n_issues']} issue days, {split['train']['first']} to {split['train']['last']}",
        f"- Validation: {split['val']['n_issues']} issue days, {split['val']['first']} to {split['val']['last']}",
        f"- Test: {split['test']['n_issues']} issue days, {split['test']['first']} to {split['test']['last']}",
        "",
        "## Features",
        "",
        "Known at the issue time (local midnight). The training target is pv_kw / system_kw.",
        "",
        ", ".join(record["features"]) + ".",
        "",
        "## Baseline",
        "",
        (
            f"Plane-of-array irradiance times system kW times {record['baseline']['loss_factor']}. "
            "The factor was not fitted. Night is zero. Output is clipped to the nameplate."
        ),
        "",
        "## Parameters",
        "",
        f"- Boosting rounds requested: {record['n_estimators_requested']}",
        f"- Best iteration: {record['best_iteration']}",
        f"- Early stopping: {record['early_stopping_rounds']} rounds",
    ]
    for key, value in record["params"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Test metrics", "", record["nmae_definition"] + ".", ""])
    lines.append("| slice | model | n | MAE kW | RMSE kW | nMAE |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for slice_name, block in record["metrics"]["test"].items():
        for model_name in ("baseline", "lightgbm"):
            item = block[model_name]
            lines.append(
                "| {slice} | {model} | {n} | {mae} | {rmse} | {nmae} |".format(
                    slice=slice_name,
                    model=model_name,
                    n=item["n"],
                    mae=_num(item["mae_kw"]),
                    rmse=_num(item["rmse_kw"]),
                    nmae=_num(item["nmae"]),
                )
            )
    lines.extend(
        [
            "",
            f"Cloudy slice: {record['cloudy_definition']}",
            "",
            f"Midday slice: {record['midday_definition']}",
            "",
            "## Result",
            "",
            record["verdict"],
            "",
            f"Git sha `{record['git_sha']}`. LightGBM {record['library_versions']['lightgbm']}, "
            f"pvlib {record['library_versions']['pvlib']}.",
            "",
        ]
    )
    return "\n".join(lines)


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return "unknown"


def verdict(beats: bool, test_metrics: dict) -> str:
    base = test_metrics["overall"]["baseline"]["mae_kw"]
    model = test_metrics["overall"]["lightgbm"]["mae_kw"]
    if base is None or model is None:
        return "Test MAE could not be computed."
    if beats:
        sentence = (
            f"LightGBM test MAE is {model:.4f} kW. "
            f"The baseline is {base:.4f} kW. LightGBM is ahead on this run."
        )
    else:
        sentence = (
            f"LightGBM test MAE is {model:.4f} kW. "
            f"The baseline is {base:.4f} kW. "
            "LightGBM does not beat the physics baseline on test MAE."
        )
    extra = []
    for slice_name in ("cloudy", "midday"):
        block = test_metrics[slice_name]
        if block["lightgbm"]["n"] == 0:
            extra.append(f"The {slice_name} slice has no rows.")
            continue
        ahead = block["lightgbm"]["mae_kw"] < block["baseline"]["mae_kw"]
        word = "ahead of" if ahead else "not ahead of"
        extra.append(
            f"On {slice_name} hours LightGBM is {word} the baseline "
            f"({block['lightgbm']['mae_kw']:.4f} vs {block['baseline']['mae_kw']:.4f} kW MAE)."
        )
    return sentence + " " + " ".join(extra)


def _drop_incomplete(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    ok = np.ones(len(frame), dtype=bool)
    for column in ("pv_kw", "system_kw", "solar_elevation_deg", *WEATHER_COLUMNS):
        ok &= np.isfinite(pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float))
    return frame.loc[ok].reset_index(drop=True), int((~ok).sum())


def _target(frame: pd.DataFrame) -> np.ndarray:
    return frame["pv_kw"].to_numpy(dtype=float) / frame["system_kw"].to_numpy(dtype=float)


def _score_part(part: pd.DataFrame, predicted: np.ndarray) -> dict:
    masks = slice_masks(part)
    predicted = np.asarray(predicted, dtype=float)
    actual = part["pv_kw"].to_numpy(dtype=float)
    base = part["baseline_kw"].to_numpy(dtype=float)
    size = part["system_kw"].to_numpy(dtype=float)
    return {
        name: {
            "baseline": score(actual[mask], base[mask], size[mask]),
            "lightgbm": score(actual[mask], predicted[mask], size[mask]),
        }
        for name, mask in masks.items()
    }


def _beats(overall: dict) -> bool:
    base = overall["baseline"]["mae_kw"]
    model = overall["lightgbm"]["mae_kw"]
    if base is None or model is None:
        return False
    return bool(model < base)


def _fmt(block: dict) -> str:
    if block["n"] == 0 or block["mae_kw"] is None:
        return "n=0"
    return (
        f"n={block['n']}  MAE {block['mae_kw']:.4f} kW  "
        f"RMSE {block['rmse_kw']:.4f} kW  nMAE {block['nmae']:.4f}"
    )


def _num(value) -> str:
    if value is None:
        return ""
    return f"{value:.4f}"


def _jsonable(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
