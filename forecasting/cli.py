"""Train, score and write a 24-hour PV forecast.

    python -m forecasting train --synthetic
    python -m forecasting forecast --model forecasting/models/<version> --site home-dehiwala --date 2024-08-01 --readings ... --weather ...
    python -m forecasting fetch-weather --sites forecasting/sites.example.csv --start 2024-06-01 --end 2024-06-03 --kind historical

The forecast file is for the scheduler to read. This program does not control equipment.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import lightgbm as lgb
import pandas as pd
import requests

from data.pipeline.tables import parse_date
from forecasting.baseline import baseline_power
from forecasting.config import (
    BASELINE_LOSS_FACTOR,
    DEFAULT_N_ESTIMATORS,
    DEFAULT_SYNTHETIC_END,
    DEFAULT_SYNTHETIC_START,
    EXAMPLE_SITES,
    FORECAST_DIR,
    MODEL_DIR,
    TIMEZONE,
    WEATHER_CACHE_DIR,
    WORK_DIR,
)
from forecasting.features import build_frame, infer_resolution
from forecasting.model import format_report, predict_kw, train_and_evaluate, write_forecasts
from forecasting.synthetic import generate_simulated
from forecasting.tables import load_readings, load_sites, load_weather_table, write_table
from forecasting.weather import fetch_weather


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m forecasting",
        description=(
            "Forecast rooftop PV AC power for the next 24 hours. "
            "Writes a file. Does not command an inverter."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    train = sub.add_parser(
        "train",
        help="Fit LightGBM, score it against the physics baseline, write forecasts.",
    )
    train.add_argument(
        "--synthetic",
        action="store_true",
        help="Build a SIMULATED series (clear-sky times a cloud factor, plus noise) and train on that.",
    )
    train.add_argument("--start", default=DEFAULT_SYNTHETIC_START, help="First day, YYYY-MM-DD. Default %(default)s.")
    train.add_argument("--end", default=DEFAULT_SYNTHETIC_END, help="Last day, YYYY-MM-DD, inclusive. Default %(default)s.")
    train.add_argument("--resolution", choices=["hourly", "15min"], default="hourly")
    train.add_argument("--seed", type=int, default=7)
    train.add_argument("--sites", type=Path, default=EXAMPLE_SITES, help="Site metadata CSV. Default %(default)s.")
    train.add_argument("--readings", type=Path, default=None, help="Edge-unit CSV, or a directory of them. Required unless --synthetic.")
    train.add_argument("--weather", type=Path, default=None, help="Weather CSV with site_id or location_id. Required unless --synthetic.")
    train.add_argument("--model-dir", type=Path, default=MODEL_DIR)
    train.add_argument("--forecast-dir", type=Path, default=FORECAST_DIR)
    train.add_argument("--work-dir", type=Path, default=WORK_DIR, help="Where --synthetic writes its CSV files.")
    train.add_argument("--estimators", type=int, default=DEFAULT_N_ESTIMATORS)
    train.add_argument("--learning-rate", type=float, default=None)
    train.add_argument("--num-leaves", type=int, default=None)
    train.add_argument("--loss-factor", type=float, default=BASELINE_LOSS_FACTOR)
    train.set_defaults(func=cmd_train)

    forecast = sub.add_parser(
        "forecast",
        help="Write one site's next 24 hours from a saved model.",
    )
    forecast.add_argument("--model", type=Path, required=True, help="Version directory from train.")
    forecast.add_argument("--site", required=True, help="site_id.")
    forecast.add_argument("--date", required=True, help="Issue date, YYYY-MM-DD, Asia/Colombo. Covers that local day.")
    forecast.add_argument("--sites", type=Path, default=EXAMPLE_SITES)
    forecast.add_argument("--readings", type=Path, required=True, help="History used for lags. Rows on the issue date are not used as features.")
    forecast.add_argument("--weather", type=Path, required=True, help="Forecast weather covering the issue date.")
    forecast.add_argument("--forecast-dir", type=Path, default=FORECAST_DIR)
    forecast.set_defaults(func=cmd_forecast)

    fetch = sub.add_parser(
        "fetch-weather",
        help="Download Open-Meteo weather for the sites and cache it.",
    )
    fetch.add_argument("--sites", type=Path, default=EXAMPLE_SITES)
    fetch.add_argument("--start", required=True)
    fetch.add_argument("--end", required=True)
    fetch.add_argument("--kind", choices=["forecast", "historical"], required=True)
    fetch.add_argument("--resolution", choices=["hourly", "15min"], default="hourly")
    fetch.add_argument("--cache-dir", type=Path, default=WEATHER_CACHE_DIR)
    fetch.set_defaults(func=cmd_fetch)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (ValueError, FileNotFoundError, requests.HTTPError, requests.Timeout) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_train(args: argparse.Namespace) -> None:
    start = parse_date(args.start)
    end = parse_date(args.end)
    if args.synthetic:
        sites = load_sites(args.sites)
        readings, weather = generate_simulated(
            sites,
            start,
            end,
            args.resolution,
            seed=args.seed,
        )
        _write_simulated(args.work_dir, sites, readings, weather, args.resolution, args.seed)
    else:
        if args.readings is None or args.weather is None:
            raise ValueError("Pass --readings and --weather, or use --synthetic.")
        sites = load_sites(args.sites)
        readings = load_readings(args.readings)
        weather = load_weather_table(args.weather)
    frame = build_frame(readings, sites, weather)
    params = {}
    if args.learning_rate is not None:
        params["learning_rate"] = args.learning_rate
    if args.num_leaves is not None:
        params["num_leaves"] = args.num_leaves
    record = train_and_evaluate(
        frame,
        model_dir=args.model_dir,
        forecast_dir=args.forecast_dir,
        resolution=args.resolution,
        n_estimators=args.estimators,
        params=params or None,
        loss_factor=args.loss_factor,
        seed=args.seed,
    )
    print(format_report(record), end="", flush=True)


def cmd_forecast(args: argparse.Namespace) -> None:
    model_dir = args.model
    experiment = json.loads((model_dir / "experiment.json").read_text(encoding="utf-8"))
    version = experiment["model_version"]
    resolution = experiment["data_window"]["resolution"]
    loss_factor = float(experiment["baseline"]["loss_factor"])
    booster = lgb.Booster(model_file=str(model_dir / "model.txt"))
    sites = load_sites(args.sites)
    sites = sites.loc[sites["site_id"] == args.site].copy()
    if sites.empty:
        raise ValueError(f"No site {args.site!r} in {args.sites}")
    day = parse_date(args.date)
    issued = pd.Timestamp(datetime(day.year, day.month, day.day), tz=TIMEZONE)
    readings = load_readings(args.readings)
    readings = readings.loc[readings["site_id"] == args.site].copy()
    if readings.empty:
        raise ValueError(f"No readings for {args.site}")
    weather = load_weather_table(args.weather)
    if "site_id" in weather.columns:
        weather = weather.loc[weather["site_id"] == args.site].copy()
        if weather.empty:
            raise ValueError(f"No weather rows for {args.site}")
    frame = build_frame(readings, sites, weather)
    day_frame = frame.loc[frame["issued_at"] == issued].copy()
    if day_frame.empty:
        raise ValueError(f"No joined rows for {args.site} on {args.date}")
    seen = infer_resolution(day_frame)
    if seen != resolution:
        raise ValueError(f"The saved model is {resolution} and these timestamps are {seen}.")
    day_frame["baseline_kw"] = baseline_power(day_frame, loss_factor).to_numpy()
    predicted = predict_kw(booster, day_frame)
    root = write_forecasts(
        day_frame,
        predicted,
        version=version,
        forecast_dir=args.forecast_dir,
        resolution=resolution,
    )
    label = "SIMULATED" if bool(day_frame["is_simulated"].any()) else "MEASURED"
    print(
        f"Data: {label}. Wrote {root / args.site / (args.date + '.csv')}. "
        "This command does not control any equipment.",
        flush=True,
    )


def cmd_fetch(args: argparse.Namespace) -> None:
    sites = load_sites(args.sites)
    frame = fetch_weather(
        sites,
        parse_date(args.start),
        parse_date(args.end),
        kind=args.kind,
        resolution=args.resolution,
        cache_dir=args.cache_dir,
    )
    print(
        f"Wrote {len(frame)} weather rows for {frame['site_id'].nunique()} sites "
        f"under {args.cache_dir}. Kind: {args.kind}.",
        flush=True,
    )


def _write_simulated(work_dir: Path, sites, readings, weather, resolution: str, seed: int) -> None:
    note = {
        "project": "Rooftops to Power Plant",
        "data_label": "SIMULATED",
        "is_simulated": True,
        "controls_equipment": False,
        "resolution": resolution,
        "seed": seed,
        "note": (
            "SIMULATED. pvlib clear-sky irradiance times a cloud factor, "
            "a temperature loss and noise. Not an inverter log."
        ),
    }
    write_table(sites, work_dir / "sites.csv", {**note, "table": "sites"})
    write_table(readings, work_dir / "readings.csv", {**note, "table": "readings", "rows": int(len(readings))})
    write_table(
        weather,
        work_dir / "weather.csv",
        {
            **note,
            "table": "weather",
            "rows": int(len(weather)),
            "note": (
                "SIMULATED forecast weather. A noisy copy of the weather that drove "
                "the simulated inverter. The exact driving series is not in this file."
            ),
        },
    )


if __name__ == "__main__":
    raise SystemExit(main())
