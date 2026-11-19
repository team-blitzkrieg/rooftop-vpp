"""In-memory store used by tests and by local runs without DATABASE_URL."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from api.util import hash_key, parse_time


class MemoryStore:
    def __init__(self):
        self.sites: dict[str, dict] = {}
        self.devices: dict[str, dict] = {}
        self.readings: list[dict] = []
        self.runs: list[dict] = []
        self.forecasts: list[dict] = []
        self.models: list[dict] = []
        self.faults: list[dict] = []
        self._run_seq = 0

    def add_site(self, site_id: str, **fields) -> None:
        row = {"site_id": site_id, "timezone": "Asia/Colombo", "has_meter": True}
        row.update(fields)
        self.sites[site_id] = row

    def add_device(self, device_id: str, site_id: str, raw_key: str) -> None:
        if site_id not in self.sites:
            self.add_site(site_id)
        self.devices[hash_key(raw_key)] = {"device_id": device_id, "site_id": site_id}

    def site_for_key(self, raw_key: str) -> str | None:
        row = self.devices.get(hash_key(raw_key))
        return None if row is None else row["site_id"]

    def upsert_reading(
        self,
        site_id: str,
        timestamp,
        *,
        pv_kw=None,
        consumption_kw=None,
        import_kw=None,
        export_kw=None,
        data_label="MEASURED",
        is_simulated=False,
    ) -> None:
        stamp = parse_time(timestamp)
        self.readings = [
            row
            for row in self.readings
            if not (row["site_id"] == site_id and row["timestamp"] == stamp)
        ]
        self.readings.append(
            {
                "site_id": site_id,
                "timestamp": stamp,
                "pv_kw": pv_kw,
                "consumption_kw": consumption_kw,
                "import_kw": import_kw,
                "export_kw": export_kw,
                "data_label": data_label,
                "is_simulated": bool(is_simulated),
            }
        )

    def reading_count(self, site_id: str | None = None) -> int:
        if site_id is None:
            return len(self.readings)
        return sum(1 for row in self.readings if row["site_id"] == site_id)

    def list_sites(self) -> list[dict]:
        return list(self.sites.values())

    def readings_for(self, site_id: str, *, include_simulated: bool) -> list[dict]:
        rows = [row for row in self.readings if row["site_id"] == site_id]
        if not include_simulated:
            rows = [row for row in rows if not row["is_simulated"]]
        return rows

    def issue_day_count(self, *, include_simulated: bool) -> int:
        days = set()
        for row in self.readings:
            if row["is_simulated"] and not include_simulated:
                continue
            days.add(parse_time(row["timestamp"]).tz_convert("Asia/Colombo").date())
        return len(days)

    def record_run(
        self,
        site_id: str,
        target: str,
        status: str,
        *,
        issued_at=None,
        model_version=None,
        message=None,
    ) -> int:
        if status not in {"success", "failed"}:
            raise ValueError("status must be success or failed")
        self._run_seq += 1
        self.runs.append(
            {
                "run_id": self._run_seq,
                "site_id": site_id,
                "target": target,
                "issued_at": None if issued_at is None else parse_time(issued_at),
                "status": status,
                "model_version": model_version,
                "message": message,
                "created_at": datetime.now(timezone.utc),
            }
        )
        return self._run_seq

    def publish_forecast(
        self,
        site_id: str,
        target: str,
        issued_at,
        rows: list[dict],
        *,
        model_version: str,
        run_id: int,
        resolution: str,
        data_label: str,
        is_simulated: bool,
    ) -> None:
        """Replace this issue only. Older successful issues stay until retention."""
        issued = parse_time(issued_at)
        self.forecasts = [
            row
            for row in self.forecasts
            if not (
                row["site_id"] == site_id
                and row["target"] == target
                and row["issued_at"] == issued
            )
        ]
        for row in rows:
            self.forecasts.append(
                {
                    "site_id": site_id,
                    "target": target,
                    "timestamp": parse_time(row["timestamp"]),
                    "issued_at": issued,
                    "lead_hours": row.get("lead_hours"),
                    "value_kw": float(row["value_kw"]),
                    "baseline_kw": row.get("baseline_kw"),
                    "net_kw": row.get("net_kw"),
                    "model_version": model_version,
                    "run_id": run_id,
                    "resolution": resolution,
                    "data_label": data_label,
                    "is_simulated": bool(is_simulated),
                }
            )

    def latest_run(self, site_id: str, target: str) -> dict | None:
        found = [row for row in self.runs if row["site_id"] == site_id and row["target"] == target]
        if not found:
            return None
        return max(found, key=lambda row: (row["created_at"], row["run_id"]))

    def latest_success(self, site_id: str, target: str) -> dict | None:
        found = [
            row
            for row in self.runs
            if row["site_id"] == site_id and row["target"] == target and row["status"] == "success"
        ]
        found.sort(key=lambda row: (row["created_at"], row["run_id"]), reverse=True)
        for run in found:
            rows = [
                row
                for row in self.forecasts
                if row["site_id"] == site_id
                and row["target"] == target
                and row["issued_at"] == run["issued_at"]
                and row["run_id"] == run["run_id"]
            ]
            if not rows:
                continue
            rows.sort(key=lambda row: row["timestamp"])
            return {**run, "rows": rows}
        return None

    def insert_model(
        self,
        version: str,
        target: str,
        metrics: dict | None,
        *,
        promoted: bool,
        artefact_url: str | None,
        git_sha: str | None,
    ) -> None:
        if promoted:
            for row in self.models:
                if row["target"] == target:
                    row["promoted"] = False
        self.models = [row for row in self.models if row["version"] != version]
        self.models.append(
            {
                "version": version,
                "target": target,
                "metrics": metrics,
                "promoted": bool(promoted),
                "artefact_url": artefact_url,
                "git_sha": git_sha,
                "created_at": datetime.now(timezone.utc),
            }
        )

    def promoted_model(self, target: str) -> dict | None:
        found = [row for row in self.models if row["target"] == target and row["promoted"]]
        return found[-1] if found else None

    def save_fault(
        self,
        site_id: str,
        rule: str,
        status: str,
        *,
        detail: str,
        data_label: str,
        is_simulated: bool,
        checked_at=None,
    ) -> None:
        moment = checked_at or datetime.now(timezone.utc)
        self.faults = [
            row for row in self.faults if not (row["site_id"] == site_id and row["rule"] == rule)
        ]
        self.faults.append(
            {
                "site_id": site_id,
                "rule": rule,
                "status": status,
                "detail": detail,
                "checked_at": moment,
                "data_label": data_label,
                "is_simulated": bool(is_simulated),
            }
        )

    def list_faults(self, site_id: str | None = None) -> list[dict]:
        rows = self.faults if site_id is None else [row for row in self.faults if row["site_id"] == site_id]
        return sorted(rows, key=lambda row: (row["site_id"], row["rule"]))

    def prune(self, *, now=None, reading_days: int = 90, forecast_days: int = 30) -> None:
        moment = now or datetime.now(timezone.utc)
        reading_cut = moment - timedelta(days=reading_days)
        forecast_cut = moment - timedelta(days=forecast_days)
        self.readings = [row for row in self.readings if row["timestamp"] >= reading_cut]
        keep_issued = set()
        for site_id in {row["site_id"] for row in self.forecasts}:
            for target in {row["target"] for row in self.forecasts if row["site_id"] == site_id}:
                success = self.latest_success(site_id, target)
                if success is not None:
                    keep_issued.add((site_id, target, success["issued_at"]))
        self.forecasts = [
            row
            for row in self.forecasts
            if row["timestamp"] >= forecast_cut
            or (row["site_id"], row["target"], row["issued_at"]) in keep_issued
        ]
