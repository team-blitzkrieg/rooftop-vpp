# Contributing

Mithil Rajapakse, Tatiana Armstrong and Senesh Fernando all commit here. `main` should stay in a state we would show a judge.

## Branches

1. Update `main` before you start.
2. Branch from `main`. Name the branch with your name and the work, for example `mithil/lv-network` or `senesh/demand-forecast`.
3. Keep one branch to one piece of work. Open a second branch if the work splits.

## Pull requests

1. Open a pull request into `main`.
2. In the description, say what changed, how you checked it, and what is still unfinished.
3. Ask one of the other two to review it before merging. Do not merge a pull request that only you have read.
4. Edge Unit changes need a review from Tatiana or Mithil. Forecasting, the scheduler and the dashboard need a review from Senesh. Anything that changes a tariff figure or a grid limit needs a review from Mithil.

## What not to commit

- Pilot inverter logs, or any other private file, dropped in `data/raw/` or `data/processed/` outside `weather/`, `live/` and `pv_simulated/`. Those loose files are gitignored. The weather downloads and the simulated PV tables in those three folders are meant to be committed.
- Anything in `data/sample/` that is not a small anonymised example.
- Trained model files. They are gitignored. Rebuild them from the scripts instead.
- `.env` files, passwords and API keys.
- Personal phone numbers or email addresses.
