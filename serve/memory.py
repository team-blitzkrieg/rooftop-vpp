"""In-memory store for tests. The compose stack uses PostgresStore."""

from __future__ import annotations

from serve.clock import parse_time, utcnow
from serve.tokens import hash_token


class MemoryStore:
    def __init__(self):
        self.sites: dict[str, dict] = {}
        self.devices: dict[str, dict] = {}
        self.readings_rows: list[dict] = []
        self.runs: list[dict] = []
        self.forecasts: list[dict] = []
        self._seq = 0

    def ping(self) -> bool:
        return True

    def migrate(self) -> None:
        return None

    def upsert_site(self, row: dict) -> None:
        self.sites[row["site_id"]] = dict(row)

    def list_sites(self) -> list[dict]:
        return [dict(row) for row in self.sites.values()]

    def add_device(self, device_id: str, site_id: str, token: str) -> None:
        self.devices[hash_token(token)] = {"device_id": device_id, "site_id": site_id}

    def site_for_token(self, token: str) -> str | None:
        row = self.devices.get(hash_token(token))
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
        self.readings_rows = [
            row
            for row in self.readings_rows
            if not (row["site_id"] == site_id and row["timestamp"] == stamp)
        ]
        self.readings_rows.append(
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

    def readings(self, site_id: str, limit: int = 500) -> list[dict]:
        rows = [row for row in self.readings_rows if row["site_id"] == site_id]
        rows.sort(key=lambda row: row["timestamp"], reverse=True)
        return rows[: int(limit)]

    def all_readings(self) -> list[dict]:
        return sorted(self.readings_rows, key=lambda row: (row["site_id"], row["timestamp"]))

    def record_failure(self, site_id: str, target: str, message: str, *, issued_at=None, model_version=None) -> int:
        self._seq += 1
        self.runs.append(
            {
                "run_id": self._seq,
                "site_id": site_id,
                "target": target,
                "issued_at": None if issued_at is None else parse_time(issued_at),
                "status": "failed",
                "model_version": model_version,
                "message": message,
                "created_at": utcnow(),
            }
        )
        return self._seq

    def publish_success(
        self,
        site_id: str,
        target: str,
        issued_at,
        rows: list[dict],
        *,
        model_version: str,
        data_label: str,
        is_simulated: bool,
    ) -> int:
        issued = parse_time(issued_at)
        self._seq += 1
        run_id = self._seq
        self.runs.append(
            {
                "run_id": run_id,
                "site_id": site_id,
                "target": target,
                "issued_at": issued,
                "status": "success",
                "model_version": model_version,
                "message": None,
                "created_at": utcnow(),
            }
        )
        self.forecasts = [
            row
            for row in self.forecasts
            if not (row["site_id"] == site_id and row["target"] == target and row["issued_at"] == issued)
        ]
        for row in rows:
            self.forecasts.append(
                {
                    "site_id": site_id,
                    "target": target,
                    "timestamp": parse_time(row["timestamp"]),
                    "issued_at": issued,
                    "value_kw": float(row["value_kw"]),
                    "model_version": model_version,
                    "run_id": run_id,
                    "data_label": data_label,
                    "is_simulated": bool(is_simulated),
                }
            )
        return run_id

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
                if row["run_id"] == run["run_id"]
            ]
            if not rows:
                continue
            rows.sort(key=lambda row: row["timestamp"])
            return {**run, "rows": rows}
        return None
