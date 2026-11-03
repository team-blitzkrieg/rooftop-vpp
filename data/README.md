# Data

Owner: Senesh Fernando (software), for the folder layout and any later download scripts. Mithil Rajapakse says what the inverter columns mean. Tatiana Armstrong will drop captures from the Edge Unit into `raw/` during the pilot.

## Purpose

Weather, tariffs and inverter logs. Logs from the pilot home are private. They stay on disk and out of git.

## Layout

- `raw/` holds files as collected. Git ignores everything here except `.gitkeep`. Do not commit pilot logs.
- `processed/` holds cleaned tables the models will read. Same rule: ignored, except `.gitkeep`.
- `sample/` holds small anonymised examples that are safe to commit, so the column layout is visible without the real logs. This folder is tracked. It is empty apart from `.gitkeep` until we have a sample worth sharing.

## Planned contents

- Inverter logs from the pilot home, in `raw/` only
- Open-Meteo and NASA POWER weather pulls
- The published CEB tariff, as a small table
- A note beside each file in `sample/` describing the columns, once a real anonymised extract exists

Nothing has been collected into the repository yet.
