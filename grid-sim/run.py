"""Run the 50-home study and save the tables and the chart.

From the repository root:

    python grid-sim/run.py            # full year, about 10 minutes
    python grid-sim/run.py --quick    # 6 weeks, about 1 minute, for a smoke test

Outputs go to grid-sim/results/. Everything is simulated.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from gridsim import demand  # noqa: E402
from gridsim.feeder import FeederConfig  # noqa: E402
from gridsim.simulate import PV_SIZE_PROBABILITY, PV_SIZES_KW, Scenario, load_pv_per_kw, run_scenario  # noqa: E402

SOLAR_SHARES = (0.2, 0.4, 0.6, 0.8, 1.0)
MAIN_SHARE = 0.6
SENSITIVITY_SOURCE_PU = 1.00


def _run(job: tuple[str, Scenario, bool]) -> tuple[str, dict]:
    label, scenario, quick = job
    per_kw = None
    if quick:
        full = load_pv_per_kw(scenario)
        per_kw = pd.concat([full.loc[f"{scenario.year}-03-01":f"{scenario.year}-03-28"],
                            full.loc[f"{scenario.year}-10-01":f"{scenario.year}-10-14"]])
    return label, run_scenario(scenario, per_kw)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    jobs = [(f"share_{int(s * 100)}", Scenario(solar_share=s), args.quick) for s in SOLAR_SHARES]
    sensitivity = Scenario(
        solar_share=MAIN_SHARE, feeder=replace(FeederConfig(), source_voltage_pu=SENSITIVITY_SOURCE_PU)
    )
    jobs.append(("sensitivity_source_1.00pu", sensitivity, args.quick))

    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        results = dict(pool.map(_run, jobs))

    out = HERE / ("results_quick" if args.quick else "results")
    out.mkdir(exist_ok=True)

    rows = []
    for label, result in results.items():
        for row in result["summary"]:
            rows.append({"run": label, "source_voltage_pu": result["scenario"]["feeder"]["source_voltage_pu"]} | row)
    summary = pd.DataFrame(rows)
    summary.to_csv(out / "summary.csv", index=False)
    model = pd.DataFrame([{"run": k} | v["model_test"] for k, v in results.items()])
    model.to_csv(out / "voltage_model_test.csv", index=False)

    main_run = results[f"share_{int(MAIN_SHARE * 100)}"]
    hourly = pd.concat(
        {name: table[["v_max_pu", "trafo_loading_pct", "trafo_p_kw", "pv_available_kw", "pv_used_kw", "export_share"]]
         for name, table in main_run["cases"].items()},
        axis=1,
    ).round(4)
    hourly.columns = [f"{case}__{column}" for case, column in hourly.columns]
    hourly.to_csv(out / f"hourly_share_{int(MAIN_SHARE * 100)}.csv", index_label="timestamp")

    meta = {
        "project": "Rooftops to Power Plant",
        "is_simulated": True,
        "is_measured": False,
        "note": "Simulated neighbourhood, simulated solar, simulated demand. Not a study of a real feeder.",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "quick_run": args.quick,
        "script": "grid-sim/run.py",
        "scenario_defaults": main_run["scenario"],
        "feeder": FeederConfig().describe(),
        "demand_assumptions": demand.ASSUMPTIONS,
        "pv_sizes_kw": dict(zip(map(str, PV_SIZES_KW), PV_SIZE_PROBABILITY)),
        "pv_data": "data/processed/pv_simulated/open_meteo_archive/colombo.csv (pvlib model, not meter data)",
        "control_tested_on": "September to December (the voltage model is fitted on January to August)",
        "homes_main_run": main_run["homes"],
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2))

    chart(summary[summary["run"].str.startswith("share_")], out / "control_result.png")
    shown = summary[summary["period"] == "test_months"]
    print(shown[["run", "case", "transformer_overload_hours", "over_voltage_hours",
                 "home_hours_over_voltage", "max_voltage_v", "solar_held_back_pct",
                 "evening_peak_import_kw"]].to_string(index=False))
    print(summary[summary["period"] == "full_year"][
        ["run", "transformer_overload_hours", "transformer_max_loading_pct", "over_voltage_hours",
         "home_hours_over_voltage", "max_voltage_v", "min_voltage_v"]].to_string(index=False))
    print(model.round(3).to_string(index=False))


def chart(summary: pd.DataFrame, path: Path) -> None:
    """Two panels, one measure each: hours with a problem, with and without the export limit."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, muted, surface = "#0b0b0b", "#52514e", "#fcfcfb"
    colours = {"no_control": "#2a78d6", "limit": "#eb6834"}
    names = {"no_control": "No control", "limit": "With fair export limit"}
    test = summary[(summary["period"] == "test_months") & summary["case"].isin(colours)]
    panels = [
        ("over_voltage_hours", "Hours with a home above 243.8 V"),
        ("transformer_overload_hours", "Hours with the transformer above 100%"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), facecolor=surface)
    for ax, (column, title) in zip(axes, panels):
        table = test.pivot(index="solar_share", columns="case", values=column)[list(colours)]
        top = max(table.to_numpy().max(), 1)
        for offset, case in zip((-0.19, 0.19), colours):
            xs = [i + offset for i in range(len(table))]
            bars = ax.bar(xs, table[case], width=0.36, color=colours[case], label=names[case])
            for bar, value in zip(bars, table[case]):
                ax.text(bar.get_x() + bar.get_width() / 2, value + top * 0.015, f"{int(value)}",
                        ha="center", va="bottom", fontsize=9, color=ink)
        ax.set_xticks(range(len(table)), [f"{int(s * 100)}%" for s in table.index])
        ax.set_xlabel("Homes with rooftop solar (of 50)", color=muted)
        ax.set_title(title, loc="left", fontsize=11, color=ink)
        ax.set_ylim(0, top * 1.12)
        ax.set_facecolor(surface)
        ax.grid(axis="y", color="#e4e3df", linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(colors=muted, length=0)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color("#c9c8c2")
    axes[0].legend(frameon=False, loc="upper left", fontsize=9, labelcolor=ink)
    hours = int(test["hours"].iloc[0])
    fig.suptitle("Simulated 50-home neighbourhood, 100 kVA transformer", x=0.01, ha="left",
                 fontsize=12, color=ink, fontweight="bold")
    fig.text(0.01, 0.01,
             f"Simulated, not measured. September to December 2025 ({hours:,} hours). "
             "Source: grid-sim/run.py.", fontsize=8, color=muted)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(path, dpi=200, facecolor=surface)
    plt.close(fig)


if __name__ == "__main__":
    main()
