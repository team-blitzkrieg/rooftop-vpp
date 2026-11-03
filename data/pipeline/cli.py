"""Command line for the weather and simulated-PV pipeline.

    python -m data.pipeline fetch-weather --help
    python -m data.pipeline simulate-pv --help
    python -m data.pipeline fetch-live --help
    python -m data.pipeline write-sample --help
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from data.pipeline.config import (
    DEFAULT_ALBEDO,
    DEFAULT_AZIMUTH_DEG,
    DEFAULT_ETA_INV,
    DEFAULT_GAMMA_PDC,
    DEFAULT_START,
    DEFAULT_SYSTEM_SIZES_KW,
    DEFAULT_TILT_DEG,
    LIVE_FORECAST_URL,
    LOCATIONS,
    OPEN_METEO_ATTRIBUTION,
    OPEN_METEO_LICENCE_NAME,
    OPEN_METEO_LICENCE_URL,
    PROCESSED_PV_DIR,
    RAW_LIVE_DIR,
    RAW_WEATHER_DIR,
    SAMPLE_DIR,
    TIMEZONE,
    WEATHER_SOURCES,
    Location,
)
from data.pipeline.http_client import HttpClient
from data.pipeline.nasa_power import fetch_nasa_power, nasa_meta
from data.pipeline.open_meteo import fetch_live, fetch_open_meteo, open_meteo_meta
from data.pipeline.pvsim import pv_meta, simulate_pv
from data.pipeline.samples import export_live_snapshot, export_month
from data.pipeline.tables import order_weather, parse_date, read_weather_csv, write_dataset


def build_parser() -> argparse.ArgumentParser:
    location_lines = "\n".join(
        f"  {item.id:16} {item.latitude:.4f} N, {item.longitude:.4f} E  ({item.name})"
        for item in LOCATIONS.values()
    )
    parser = argparse.ArgumentParser(
        prog="python -m data.pipeline",
        description=(
            "Download Sri Lanka weather and build a simulated rooftop PV series. "
            "The PV values are model output, not inverter readings."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Locations (approximate city centres):\n" + location_lines,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser(
        "fetch-weather",
        help="Download historical weather for one source.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "One source per run, so reanalysis, satellite data and forecast "
            "inputs stay in separate folders. Open-Meteo archive defaults to "
            "ERA5. previous-day1 is the day-ahead forecast series."
        ),
    )
    fetch.add_argument(
        "--source",
        required=True,
        choices=sorted(WEATHER_SOURCES),
        help="Which API to call.",
    )
    fetch.add_argument("--start", default=DEFAULT_START, help="First day, YYYY-MM-DD. Default %(default)s.")
    fetch.add_argument(
        "--end",
        default=None,
        help=(
            "Last day, YYYY-MM-DD, inclusive. Default is today in Asia/Colombo "
            "minus a few days, because ERA5 and NASA POWER lag real time. "
            "See the source's default_end_lag_days."
        ),
    )
    fetch.add_argument(
        "--locations",
        default="all",
        help="Comma-separated ids, or 'all'. Default %(default)s.",
    )
    fetch.add_argument(
        "--model",
        default=None,
        help=(
            "Open-Meteo model id. Default for the archive is era5. "
            "Pass 'default' to omit the parameter and take the API's best match. "
            "Ignored for NASA POWER."
        ),
    )
    fetch.add_argument("--chunk-days", type=int, default=None, help="Days per API call. Default depends on the source.")
    fetch.add_argument("--out", type=Path, default=RAW_WEATHER_DIR, help="Output root. Default data/raw/weather.")
    _add_http_args(fetch)
    fetch.set_defaults(func=cmd_fetch_weather)

    simulate = sub.add_parser(
        "simulate-pv",
        help="Run the pvlib rooftop model on a weather CSV.",
        description=(
            "Writes pv_ac_kw_simulated and related columns. This is modelled "
            "generation, not a measured series."
        ),
    )
    simulate.add_argument(
        "--weather",
        type=Path,
        nargs="+",
        required=True,
        help="Weather CSV files, or directories that contain them.",
    )
    simulate.add_argument(
        "--sizes",
        default=",".join(str(int(size)) if size == int(size) else str(size) for size in DEFAULT_SYSTEM_SIZES_KW),
        help="AC nameplate sizes in kW, comma-separated. Default %(default)s.",
    )
    simulate.add_argument("--tilt", type=float, default=DEFAULT_TILT_DEG, help="Panel tilt from horizontal, degrees. Default %(default)s.")
    simulate.add_argument(
        "--azimuth",
        type=float,
        default=DEFAULT_AZIMUTH_DEG,
        help="Panel azimuth, pvlib convention (180 = south). Default %(default)s.",
    )
    simulate.add_argument("--albedo", type=float, default=DEFAULT_ALBEDO, help="Ground albedo. Default %(default)s.")
    simulate.add_argument("--gamma-pdc", type=float, default=DEFAULT_GAMMA_PDC, help="PVWatts temperature coefficient, per degree C. Default %(default)s.")
    simulate.add_argument("--eta-inv", type=float, default=DEFAULT_ETA_INV, help="Nominal inverter efficiency. Default %(default)s.")
    simulate.add_argument("--out", type=Path, default=PROCESSED_PV_DIR, help="Output root. Default data/processed/pv_simulated.")
    simulate.set_defaults(func=cmd_simulate_pv)

    live = sub.add_parser(
        "fetch-live",
        help="Current conditions and the next days of forecast.",
        description=(
            "Saves a timestamped folder under data/raw/live so a later cron run "
            "does not overwrite this one. Adds a simulated PV forecast unless "
            "--no-simulate is set."
        ),
    )
    live.add_argument("--locations", default="all", help="Comma-separated ids, or 'all'. Default %(default)s.")
    live.add_argument("--days", type=int, default=7, help="Open-Meteo forecast_days. Default %(default)s.")
    live.add_argument("--sizes", default="5", help="AC kW sizes for the optional PV forecast. Default %(default)s (one size, for a lighter file).")
    live.add_argument("--tilt", type=float, default=DEFAULT_TILT_DEG)
    live.add_argument("--azimuth", type=float, default=DEFAULT_AZIMUTH_DEG)
    live.add_argument("--no-simulate", action="store_true", help="Do not run the pvlib model on the forecast.")
    live.add_argument("--out", type=Path, default=RAW_LIVE_DIR, help="Output root. Default data/raw/live.")
    _add_http_args(live)
    live.set_defaults(func=cmd_fetch_live)

    sample = sub.add_parser(
        "write-sample",
        help="Copy one month and the latest live pull into data/sample.",
    )
    sample.add_argument("--month", required=True, help="Calendar month, YYYY-MM, in Asia/Colombo.")
    sample.add_argument("--location", default="colombo", help="Location id. Default %(default)s.")
    sample.add_argument("--weather-root", type=Path, default=RAW_WEATHER_DIR)
    sample.add_argument("--pv-root", type=Path, default=PROCESSED_PV_DIR)
    sample.add_argument("--live-root", type=Path, default=RAW_LIVE_DIR)
    sample.add_argument("--sample-dir", type=Path, default=SAMPLE_DIR)
    sample.add_argument(
        "--skip-live",
        action="store_true",
        help="Only write the historical month, not the live snapshot.",
    )
    sample.set_defaults(func=cmd_write_sample)
    return parser


def _add_http_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--pause", type=float, default=1.0, help="Seconds to wait between calls to the same host. Default %(default)s.")
    parser.add_argument("--retries", type=int, default=5, help="Retries after a timeout, a dropped connection, or HTTP 429/5xx. Default %(default)s.")
    parser.add_argument("--timeout", type=float, default=None, help="Seconds to wait for one HTTP response. Default depends on the command.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (ValueError, FileNotFoundError, requests.HTTPError, requests.Timeout) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_fetch_weather(args: argparse.Namespace) -> None:
    source = WEATHER_SOURCES[args.source]
    locations = resolve_locations(args.locations)
    start = parse_date(args.start)
    if args.end:
        end = parse_date(args.end)
    else:
        today = datetime.now(ZoneInfo(TIMEZONE)).date()
        end = today - timedelta(days=source.default_end_lag_days)
    model = _resolve_model(source, args.model)
    chunk_days = args.chunk_days or source.default_chunk_days
    timeout = args.timeout if args.timeout is not None else source.timeout_s
    client = HttpClient(pause_s=args.pause, max_retries=args.retries, timeout_s=timeout)
    retrieved = datetime.now(timezone.utc)
    print(
        f"{source.cli_name}: {start.isoformat()} to {end.isoformat()}, "
        f"chunk {chunk_days} days, model {model or 'API default'}",
        flush=True,
    )
    for location in locations:
        if source.kind == "open_meteo":
            frame = fetch_open_meteo(
                source,
                location,
                start,
                end,
                client,
                model=model,
                chunk_days=chunk_days,
                retrieved_at=retrieved,
            )
            meta = open_meteo_meta(source, model=model, start=start, end=end)
        elif source.kind == "nasa":
            frame = fetch_nasa_power(
                source,
                location,
                start,
                end,
                client,
                chunk_days=chunk_days,
                retrieved_at=retrieved,
            )
            meta = nasa_meta(source, start=start, end=end)
        else:
            raise ValueError(f"Unknown source kind {source.kind}")
        meta["retrieved_at_utc"] = retrieved.isoformat()
        meta["rows"] = int(len(frame))
        meta["location_id"] = location.id
        meta["location_name"] = location.name
        meta["requested_latitude"] = location.latitude
        meta["requested_longitude"] = location.longitude
        path = args.out / source.source_id / f"{location.id}.csv"
        write_dataset(frame, path, meta)
        print(
            f"Wrote {len(frame)} rows ({frame['timestamp'].min()} to {frame['timestamp'].max()}) {path}",
            flush=True,
        )


def cmd_simulate_pv(args: argparse.Namespace) -> None:
    sizes = _parse_sizes(args.sizes)
    files = weather_files(args.weather)
    if not files:
        raise FileNotFoundError("No weather CSV files found.")
    for path in files:
        weather = read_weather_csv(path)
        simulated = simulate_pv(
            weather,
            sizes_kw=sizes,
            tilt_deg=args.tilt,
            azimuth_deg=args.azimuth,
            albedo=args.albedo,
            gamma_pdc=args.gamma_pdc,
            eta_inv_nom=args.eta_inv,
        )
        for location_id, group in simulated.groupby("location_id", sort=False):
            source = str(group["weather_source"].iloc[0])
            kind = str(group["weather_data_kind"].iloc[0])
            meta = pv_meta(
                weather_source=source,
                weather_data_kind=kind,
                sizes_kw=sizes,
                tilt_deg=args.tilt,
                azimuth_deg=args.azimuth,
                albedo=args.albedo,
                gamma_pdc=args.gamma_pdc,
                eta_inv_nom=args.eta_inv,
                weather_path=str(path),
            )
            meta["rows"] = int(len(group))
            meta["location_id"] = location_id
            dest = args.out / source / f"{location_id}.csv"
            write_dataset(group, dest, meta)
            print(f"Wrote {len(group)} simulated rows to {dest}", flush=True)


def cmd_fetch_live(args: argparse.Namespace) -> None:
    locations = resolve_locations(args.locations)
    timeout = args.timeout if args.timeout is not None else 60
    client = HttpClient(pause_s=args.pause, max_retries=args.retries, timeout_s=timeout)
    retrieved = datetime.now(timezone.utc)
    stamp = retrieved.strftime("%Y%m%dT%H%M%SZ")
    sizes = _parse_sizes(args.sizes)
    for location in locations:
        print(f"  live {location.id}", flush=True)
        frames = fetch_live(
            location,
            client,
            forecast_days=args.days,
            retrieved_at=retrieved,
        )
        folder = args.out / location.id / stamp
        base_meta = {
            "project": "Rooftops to Power Plant",
            "source": "open_meteo_forecast",
            "data_kind": "forecast",
            "endpoint": LIVE_FORECAST_URL,
            "timezone": TIMEZONE,
            "forecast_days": args.days,
            "retrieved_at_utc": retrieved.isoformat(),
            "location_id": location.id,
            "location_name": location.name,
            "requested_latitude": location.latitude,
            "requested_longitude": location.longitude,
            "licence": OPEN_METEO_LICENCE_NAME,
            "licence_url": OPEN_METEO_LICENCE_URL,
            "attribution": OPEN_METEO_ATTRIBUTION,
            "note_15min": (
                "Open-Meteo says 15-minute data outside Europe and North America "
                "is interpolated from hourly values. Sri Lanka is outside those regions."
            ),
            "radiation_note": (
                "Radiation variables are the mean over the preceding interval. "
                "Temperature, humidity, cloud cover and wind are the value at the timestamp."
            ),
            "pv_is_simulated": False,
        }
        file_map = {
            "current": "current.csv",
            "hourly": "hourly.csv",
            "minutely_15": "minutely_15.csv",
        }
        written = []
        for key, filename in file_map.items():
            if key not in frames:
                continue
            frame = order_weather(frames[key])
            meta = dict(base_meta)
            meta["interval"] = key
            meta["rows"] = int(len(frame))
            meta["data_kind"] = str(frame["data_kind"].iloc[0])
            write_dataset(frame, folder / filename, meta)
            written.append(filename)
            print(f"Wrote {len(frame)} rows to {folder / filename}", flush=True)

        if not args.no_simulate:
            for key, filename in (
                ("hourly", "pv_hourly_simulated.csv"),
                ("minutely_15", "pv_minutely_15_simulated.csv"),
            ):
                if key not in frames:
                    continue
                weather = order_weather(frames[key])
                simulated = simulate_pv(
                    weather,
                    sizes_kw=sizes,
                    tilt_deg=args.tilt,
                    azimuth_deg=args.azimuth,
                )
                meta = pv_meta(
                    weather_source="open_meteo_forecast",
                    weather_data_kind="forecast",
                    sizes_kw=sizes,
                    tilt_deg=args.tilt,
                    azimuth_deg=args.azimuth,
                    albedo=DEFAULT_ALBEDO,
                    gamma_pdc=DEFAULT_GAMMA_PDC,
                    eta_inv_nom=DEFAULT_ETA_INV,
                    weather_path=str(folder / file_map[key]),
                )
                meta["interval"] = key
                meta["rows"] = int(len(simulated))
                meta["location_id"] = location.id
                meta["retrieved_at_utc"] = retrieved.isoformat()
                write_dataset(simulated, folder / filename, meta)
                written.append(filename)
                print(f"Wrote {len(simulated)} simulated rows to {folder / filename}", flush=True)

        summary = dict(base_meta)
        summary["files"] = written
        summary["pv_simulated_included"] = not args.no_simulate
        summary["note"] = (
            "Index for one live pull. current, hourly and minutely_15 are "
            "forecast weather. Files named pv_*_simulated are pvlib output, "
            "not measured generation."
        )
        (folder / "meta.json").write_text(
            json.dumps(summary, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Live snapshot {folder}", flush=True)


def cmd_write_sample(args: argparse.Namespace) -> None:
    if args.location not in LOCATIONS:
        raise ValueError(
            f"Unknown location {args.location!r}. Known: {', '.join(LOCATIONS)}"
        )
    export_month(
        month=args.month,
        location_id=args.location,
        weather_root=args.weather_root,
        pv_root=args.pv_root,
        sample_dir=args.sample_dir,
    )
    if not args.skip_live:
        export_live_snapshot(
            location_id=args.location,
            live_root=args.live_root,
            sample_dir=args.sample_dir,
        )


def resolve_locations(text: str) -> list[Location]:
    cleaned = text.strip().lower()
    if cleaned == "all":
        return list(LOCATIONS.values())
    ids = [part.strip().lower() for part in cleaned.split(",") if part.strip()]
    if not ids:
        raise ValueError("Pass at least one location id, or 'all'.")
    unknown = [item for item in ids if item not in LOCATIONS]
    if unknown:
        raise ValueError(
            f"Unknown location(s): {', '.join(unknown)}. Known: {', '.join(LOCATIONS)}."
        )
    return [LOCATIONS[item] for item in ids]


def weather_files(paths: list[Path]) -> list[Path]:
    found: list[Path] = []
    for path in paths:
        if path.is_dir():
            found.extend(sorted(item for item in path.rglob("*.csv") if item.is_file()))
        elif path.is_file():
            found.append(path)
        else:
            raise FileNotFoundError(f"Not found: {path}")
    return found


def _parse_sizes(text: str) -> tuple[float, ...]:
    sizes = tuple(float(part) for part in text.split(",") if part.strip())
    if not sizes or any(size <= 0 for size in sizes):
        raise ValueError(f"System sizes must be positive kW, got {text!r}")
    return sizes


def _resolve_model(source, requested: str | None) -> str | None:
    if source.kind != "open_meteo":
        return None
    chosen = source.default_model if requested is None else requested
    if chosen is None or chosen == "default":
        return None
    return chosen


if __name__ == "__main__":
    raise SystemExit(main())
