# Data

Owner: Senesh Fernando (software), for the download scripts and the folder layout. Mithil Rajapakse says what the inverter columns mean. Tatiana Armstrong will drop captures from the Edge Unit into `raw/` during the pilot.

## Purpose

Weather for the forecast, and a simulated rooftop PV series to train on until the pilot inverter logs exist in February 2027. There is no public Sri Lankan rooftop generation dataset in this repository. The `pv_*_simulated` columns are model output. They are not meter readings, and they are not a description of how much a real roof in Colombo produces.

Logs from the pilot home stay out of git. Put them in `raw/` but not inside `weather/` or `live/`. Git ignores those loose files.

## Layout

- `pipeline/` is the Python package. Run it as `python -m data.pipeline`.
- `raw/weather/` and `raw/live/` are the downloaded weather files. They are in git. A fresh `fetch-weather` overwrites that location's file for the source you asked for. It does not append.
- `processed/pv_simulated/` is the simulated PV. It is in git too. The clone is about 600 MB because of these tables.
- `sample/` is a small Colombo extract, useful if you only want to see the columns.

After a full run the files look like this:

```
data/raw/weather/<source_id>/<location_id>.csv
data/raw/weather/<source_id>/<location_id>.meta.json
data/raw/live/<location_id>/<YYYYMMDDTHHMMSSZ>/
data/processed/pv_simulated/<source_id>/<location_id>.csv
```

`<source_id>` is one of `open_meteo_archive`, `nasa_power`, `open_meteo_historical_forecast`, `open_meteo_previous_day1`. Forecast inputs are not mixed into the reanalysis folder.

## Setup

From the repository root, with Python 3.12 (3.11 or newer is enough):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, activate with `.venv\Scripts\activate`. No API key is required.

Tests do not call the network:

```bash
python -m pytest
```

## Locations

Approximate city centres. They are the points sent to the weather APIs, not surveyed rooftops. The time zone for every file is Asia/Colombo (UTC+5:30, no daylight saving).

| id | Place | Latitude | Longitude |
| --- | --- | --- | --- |
| colombo | Colombo | 6.9271 | 79.8612 |
| kandy | Kandy | 7.2906 | 80.6337 |
| jaffna | Jaffna | 9.6615 | 80.0255 |
| galle | Galle | 6.0535 | 80.2210 |
| anuradhapura | Anuradhapura | 8.3114 | 80.4037 |

`latitude` and `longitude` in the CSV are these requested points. `grid_latitude`, `grid_longitude` and `grid_elevation_m` are the cell the API actually used. Those three can differ from the city centre by a few kilometres. `grid_elevation_m` is not a surveyed site height.

## Commands

Run these from the repository root.

Historical weather. One source per command, so the folders stay separate. `--end` defaults to today in Asia/Colombo minus a few days, because ERA5 and NASA POWER lag real time. `--locations all` is the default.

```bash
python -m data.pipeline fetch-weather \
  --source open-meteo-archive \
  --start 2020-01-01 --end 2026-10-27

python -m data.pipeline fetch-weather \
  --source nasa-power \
  --start 2020-01-01 --end 2026-10-27

python -m data.pipeline fetch-weather \
  --source open-meteo-historical-forecast \
  --start 2022-01-01 --end 2026-10-27

python -m data.pipeline fetch-weather \
  --source open-meteo-previous-day1 \
  --start 2024-02-01 --end 2026-10-27
```

The archive request uses ERA5 (`--model era5`). Pass `--model default` to take Open-Meteo's own model blend instead. A Colombo pull of previous-day-1 had empty hours through January 2024 and values from 1 February 2024, which is why that command starts in February. Open-Meteo dates the Historical Forecast API from about 2021 or 2022 depending on the model. A one-day Colombo check for 1 January 2022 returned values, so the example starts then.

Calls are split into chunks, with a one-second pause between calls to the same host and retries on a timeout, a dropped connection, or HTTP 429/5xx. A 400 is not retried. `--chunk-days`, `--pause`, `--retries` and `--timeout` change that. The historical-forecast host has sometimes accepted the connection and then stalled. If a run sits there, stop it and retry with `--retries 1 --timeout 90`.

Simulated PV from those weather files. Sizes are AC nameplate kW. The default is 3, 5 and 10.

```bash
python -m data.pipeline simulate-pv --weather data/raw/weather
```

Live forecast for a cron job or, later, the Raspberry Pi. Each run writes a new timestamped folder and leaves the old ones in place.

```bash
python -m data.pipeline fetch-live --locations colombo
```

That pulls current conditions, hourly data and 15-minute data, and writes a simulated PV forecast for a 5 kW array. `--sizes 3,5,10` uses the same sizes as the historical run. `--no-simulate` skips the PV model. `--days 7` is the Open-Meteo `forecast_days` value: seven local calendar days starting at midnight.

Copy a month and the latest live pull into `data/sample` (this is the committed extract):

```bash
python -m data.pipeline write-sample --month 2024-06 --location colombo
```

A cron line, once the Pi has the repo and the virtual environment:

```bash
cd /path/to/rooftop-vpp && . .venv/bin/activate && python -m data.pipeline fetch-live --locations colombo
```

## Which weather file to train on

`open_meteo_archive` is ERA5 reanalysis. Use it when you want a consistent observed-style past. It is not what the live forecast will look like on the day.

`nasa_power` is a second radiation source (satellite irradiance and assimilated weather). It is not a forecast. Its timestamps are the start of the UTC hour, converted to Asia/Colombo, so they fall on the half hour (`00:30`, `01:30`, ...). `--start` and `--end` are still Colombo dates: the client requests one extra UTC day, then drops hours that fall outside those dates. Open-Meteo hours are labelled on the hour (`00:00`, `01:00`, ...). Do not join the two on `timestamp` until you have resampled one of them.

`open_meteo_previous_day1` is the realistic training input. Each value is what the forecast said about 24 hours before that hour (`forecast_lead_hours` is 24). Open-Meteo builds the series from successive model runs at a fixed lead. It is not one stored bulletin per run. Keep it separate from the reanalysis.

`open_meteo_historical_forecast` stitches the first hours of each forecast run into one continuous series. It tracks recent conditions and uses the same variables as the live API. It is not a day-ahead forecast. `forecast_lead_hours` is left blank on purpose. The live model should not be trained on this file and then described as if it had only seen yesterday's forecast.

## Weather columns

| Column | Meaning |
| --- | --- |
| timestamp | Time in Asia/Colombo, as the source labelled it. See the notes below on intervals. |
| location_id | `colombo`, `kandy`, `jaffna`, `galle` or `anuradhapura`. |
| latitude, longitude | City-centre point we requested. |
| grid_latitude, grid_longitude, grid_elevation_m | Cell the API used. |
| source | `open_meteo_archive`, `nasa_power`, `open_meteo_historical_forecast`, `open_meteo_previous_day1`, or `open_meteo_forecast` for a live pull. |
| data_kind | `reanalysis`, `satellite_model`, `model_initial_hours`, `forecast`, or `current`. |
| forecast_lead_hours | `24` for previous-day-1. For a live pull, hours from `retrieved_at_utc` to `timestamp` (negative if that hour is already in the past on the day of the pull). Blank for reanalysis, NASA POWER and the stitched historical forecast. |
| temp_c | Air temperature at 2 m, °C. |
| relative_humidity_pct | Relative humidity at 2 m, percent. |
| precipitation_mm | Precipitation, mm in the hour (NASA: mm per hour). |
| cloud_cover_pct | Cloud cover, percent. |
| wind_speed_ms | Wind speed at 10 m, m/s. |
| ghi_wm2 | Global horizontal irradiance (shortwave), W/m². |
| dni_wm2 | Direct normal irradiance, W/m². |
| dhi_wm2 | Diffuse horizontal irradiance, W/m². |
| direct_horizontal_wm2 | Open-Meteo beam irradiance on a horizontal plane, W/m². Blank for NASA POWER, which is not asked for a separate horizontal-beam series. |
| retrieved_at_utc | When this pipeline downloaded the file. |

Open-Meteo radiation (shortwave, direct, diffuse, direct normal) is the mean of the preceding hour. Temperature, humidity, cloud cover and wind are the value at the timestamp. NASA POWER hourly values cover the hour that starts at the timestamp. Irradiance from NASA is published as Wh/m² for that hour, which is the same number as the average W/m², so it is stored as returned. Missing NASA values (the fill `-999`) are blank, not zero. A night-time zero is a real zero.

The `.meta.json` beside each CSV repeats the source, the licence line and these interval notes.

## Simulated PV columns

`simulate-pv` keeps the weather features and adds the model output. `is_simulated` is true on every row. The power columns are named `pv_dc_kw_simulated` and `pv_ac_kw_simulated` so a later table of real inverter logs cannot be confused with this one.

| Column | Meaning |
| --- | --- |
| timestamp, location_id, latitude, longitude | Copied from the weather file. |
| weather_source, weather_data_kind | Which weather series drove the model. |
| system_kw | AC nameplate asked for, in kW. One of 3, 5 or 10 unless you passed something else. The DC array at standard test conditions is set equal to this number. That is a simple assumption, not a count of installed systems. |
| tilt_deg | Tilt from horizontal. Default 10. Sri Lanka lies at about 6°N to 10°N, so 10° is a plain year-round fixed tilt, not a survey of roofs. |
| azimuth_deg | pvlib convention: 180 is due south, 90 is east, 0 is north. Default 180. |
| inverter_ac_limit_kw | AC cap. Equal to `system_kw`. Output is clipped to it. |
| temp_c, relative_humidity_pct, precipitation_mm, cloud_cover_pct, wind_speed_ms, ghi_wm2, dni_wm2, dhi_wm2 | Weather features copied onto the row. |
| poa_global_wm2_simulated | Plane-of-array irradiance from the isotropic sky model, W/m². |
| cell_temp_c_simulated | Cell temperature from pvlib's SAPM close-mount glass/glass coefficients. |
| pv_dc_kw_simulated | DC power, PVWatts, kW. |
| pv_ac_kw_simulated | AC power after the PVWatts inverter model, kW. This is the target to train on until real logs exist. |
| is_simulated | Always true. |

The temperature coefficient is the PVWatts crystalline-silicon default, -0.004 per °C away from 25 °C. Nominal inverter efficiency is 0.96, the pvlib PVWatts default. Ground albedo is 0.2. Hours with missing irradiance, temperature or wind get a blank power, not a zero. Simulated power columns are rounded to 4 decimal places (kW).

pvlib is BSD-3-Clause: <https://pvlib-python.readthedocs.io/>.

## Live forecast files

Inside each timestamped folder:

| File | Contents |
| --- | --- |
| current.csv | One row of current conditions. Open-Meteo's current block has no radiation variables, so `ghi_wm2`, `dni_wm2` and `dhi_wm2` are blank. |
| hourly.csv | Hourly forecast for `forecast_days` local calendar days, from midnight. |
| minutely_15.csv | 15-minute forecast for the same window, when the API returns it. |
| pv_hourly_simulated.csv | Same pvlib model, driven by `hourly.csv`. |
| pv_minutely_15_simulated.csv | Same model on the 15-minute file, when that file has radiation. |
| meta.json | Source, licence, retrieval time. |

Open-Meteo says 15-minute data outside Europe and North America is interpolated from hourly data. Sri Lanka is outside those regions. The 15-minute file is still saved, with that note in the metadata.

## Sources and licences

Please keep the attribution when you publish a chart from these files.

**Open-Meteo, CC BY 4.0.** Weather data by Open-Meteo.com. Licence: <https://open-meteo.com/en/licence>.

- Historical Weather API (reanalysis): <https://open-meteo.com/en/docs/historical-weather-api>, host `archive-api.open-meteo.com`. With `--model era5` the series is ERA5, produced by ECMWF for the Copernicus Climate Change Service, also under CC BY 4.0: <https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels>.
- Historical Forecast API: <https://open-meteo.com/en/docs/historical-forecast-api>, host `historical-forecast-api.open-meteo.com`.
- Previous Runs API (day-ahead inputs): <https://open-meteo.com/en/docs/previous-runs-api>, host `previous-runs-api.open-meteo.com`.
- Forecast API (live): <https://open-meteo.com/en/docs>, host `api.open-meteo.com`.

**NASA POWER.** Hourly point API, community `RE`, time standard UTC: <https://power.larc.nasa.gov/docs/services/api/temporal/hourly/>. These data were obtained from the NASA Langley Research Center (LaRC) POWER Project funded through the NASA Earth Science/Applied Science Program. Home page: <https://power.larc.nasa.gov/>. Parameters: `T2M`, `RH2M`, `PRECTOTCORR`, `CLOUD_AMT`, `WS10M`, `ALLSKY_SFC_SW_DWN`, `ALLSKY_SFC_SW_DNI`, `ALLSKY_SFC_SW_DIFF`.

## Sample files

Committed under `data/sample/` for June 2024 in Colombo, unless a later run replaces them:

- `colombo_open_meteo_archive_2024-06.csv` and `.meta.json`
- `colombo_nasa_power_2024-06.csv` and `.meta.json`
- `colombo_open_meteo_previous_day1_2024-06.csv` and `.meta.json`
- `colombo_open_meteo_historical_forecast_2024-06.csv` and `.meta.json`, when that download succeeded
- `colombo_pv_simulated_open_meteo_archive_2024-06.csv` and `.meta.json`
- `colombo_live_current.csv`, `colombo_live_hourly.csv`, `colombo_live_minutely_15.csv`
- `colombo_live_pv_hourly_simulated.csv`, `colombo_live_pv_minutely_15_simulated.csv`
- `colombo_live.meta.json`

The sample PV file is driven by the ERA5 archive month, for all three default sizes. It is still simulated.
