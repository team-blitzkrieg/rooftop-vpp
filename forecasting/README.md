# Forecasting

Owner: Senesh Fernando (software).

## Purpose

Predict each home's PV AC output, in kW, for the next 24 hours. The scheduler reads the file. This package does not open a serial port or write to an inverter. The pilot is read-only.

One LightGBM model is trained on `pv_kw / system_kw`, so a 3 kW roof and a 10 kW roof share it. Forecasts are scaled back by the nameplate and set to zero when the sun is below the horizon.

Issue time is midnight in Asia/Colombo. The file covers that local day, hourly or every 15 minutes. Features are the clock, the day of year, solar position, forecast irradiance and cloud, temperature, system size, tilt, azimuth, and lagged output from before midnight. Same-day readings are not features.

There is no household-demand model here.

## Run it

From the repository root, with the virtual environment from the main README:

```bash
python -m forecasting train --synthetic
```

That builds a SIMULATED series, trains, prints baseline against LightGBM (MAE, RMSE, nMAE) on the test days, and writes:

- `forecasting/models/pv-lgbm-<timestamp>/` with `model.txt`, `experiment.json` and `experiment.md`
- `data/processed/forecasts/pv-lgbm-<timestamp>/<site_id>/<date>.csv`

Both of those directories are gitignored. Model files are rebuilt from this command, not committed. The printed numbers and the experiment file are for SIMULATED data. They are not pilot measurements.

nMAE is MAE in kW divided by the mean system size on the same rows. A cloudy day is one whose daylight hours average at least 60% forecast cloud. Midday is 11:00, 12:00 and 13:00.

A shorter run, still synthetic:

```bash
python -m forecasting train --synthetic --start 2024-06-01 --end 2024-06-21 --estimators 80
```

15-minute steps:

```bash
python -m forecasting train --synthetic --resolution 15min --start 2024-06-01 --end 2024-06-21
```

Sites live in `sites.example.csv`. Three houses around Colombo, with different nameplate, tilt and azimuth. Azimuth uses the pvlib convention: 180 is south, 90 is east.

Once a real log exists, put it outside git (`data/raw/`, not inside `weather/` or `live/`) and pass it in. Columns are `site_id`, `timestamp`, `pv_kw`. The weather file needs `ghi_wm2`, `dni_wm2`, `dhi_wm2`, `cloud_cover_pct`, `temp_c`, and either `site_id` or `location_id` (the city files from `data/pipeline` use `location_id`).

```bash
python -m forecasting train \
  --sites forecasting/sites.example.csv \
  --readings data/raw/inverter \
  --weather data/raw/weather/open_meteo_previous_day1/colombo.csv
```

`open_meteo_previous_day1` is the series to train on if the live model will be fed a forecast. The archive is reanalysis. See `data/README.md`.

Download weather straight into the forecast cache (Open-Meteo, no key). A second call for the same site and dates reads the cache.

```bash
python -m forecasting fetch-weather \
  --sites forecasting/sites.example.csv \
  --start 2024-06-01 --end 2024-06-07 \
  --kind historical
```

`--kind forecast` is the forecast API. `--kind historical` is the archive and is hourly only. The archive is not a day-ahead forecast.

Write one day from a saved model:

```bash
python -m forecasting forecast \
  --model forecasting/models/pv-lgbm-<timestamp> \
  --site home-dehiwala \
  --date 2024-08-01 \
  --readings data/raw/simulated_forecast/readings.csv \
  --weather data/raw/simulated_forecast/weather.csv
```

`pv_kw` in that CSV is the LightGBM forecast. `baseline_kw` is the physics baseline. `data_label` is `SIMULATED` when the inputs were generated.

## Tests

```bash
python -m pytest
```

The forecast tests do not call the network. They check the chronological split, that features ignore the issue day's own output, that the baseline is zero at night and never above the nameplate, and a short train on synthetic data.

## How the pieces work

The baseline is pvlib plane-of-array irradiance (isotropic sky) times the AC nameplate times 0.85. That 0.85 was chosen up front. It is not fitted. Night is forced to zero even if the weather file has irradiance.

The synthetic generator, used until the pilot logs are in hand, is also pvlib, and it is a different formula: clear-sky irradiance times one cloud factor, then a temperature loss, then noise. The weather file saved next to it is a noisy copy of that driving weather, which is what the model is allowed to see. Every generated row is labelled `SIMULATED`.

Training, validation and test are whole issue-days in time order. About 70% train, 15% validation, the rest test. Validation is only there for early stopping.

## Limitations

- The synthetic target is a weather model plus noise. Beating the baseline on it does not say what the error will be on a Colombo roof. If LightGBM does not beat the baseline, say so and keep the baseline.
- Real inverter logs are not in this repository. The edge unit is not wired up, and nothing here controls it.
- One issue a day, at midnight, for the next 24 hours. Not a new forecast every few minutes.
- Lags are missing for the first day or two, and whenever the readings do not go back before midnight. LightGBM accepts that missing value.
- Household demand is not modelled.
- Open-Meteo 15-minute data outside Europe and North America is interpolated from hourly data. The historical archive path here is hourly only.
- The baseline is not the PVWatts series in `data/processed/pv_simulated/`. Do not mix the two up when quoting an error.
- No search over LightGBM parameters. `num_threads` is 1 so a rerun is closer to repeatable.
- Pooled MAE is in kW, so a 10 kW roof counts for more than a 3 kW roof. nMAE divides by the mean nameplate on those rows.
