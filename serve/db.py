"""Postgres store. Readings and forecasts are Timescale hypertables."""

from __future__ import annotations

from pathlib import Path

from serve.clock import parse_time, to_py
from serve.tokens import hash_token

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


class PostgresStore:
    def __init__(self, database_url: str):
        if not database_url:
            raise RuntimeError("DATABASE_URL is not set")
        self.database_url = database_url

    def _connect(self):
        import psycopg

        return psycopg.connect(self.database_url)

    def ping(self) -> bool:
        try:
            with self._connect() as conn:
                conn.execute("select 1")
            return True
        except Exception:
            return False

    def migrate(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists schema_migrations (
                    version text primary key,
                    applied_at timestamptz not null default now()
                )
                """
            )
            applied = {
                row[0]
                for row in conn.execute("select version from schema_migrations").fetchall()
            }
            for path in sorted(MIGRATIONS.glob("*.sql")):
                if path.name in applied:
                    continue
                conn.execute(path.read_text(encoding="utf-8"))
                conn.execute(
                    "insert into schema_migrations (version) values (%s)",
                    (path.name,),
                )
            conn.commit()

    def upsert_site(self, row: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                insert into sites (
                    site_id, name, timezone, system_kw, tilt_deg, azimuth_deg,
                    latitude, longitude, location_id
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (site_id) do update set
                    name = excluded.name,
                    timezone = excluded.timezone,
                    system_kw = excluded.system_kw,
                    tilt_deg = excluded.tilt_deg,
                    azimuth_deg = excluded.azimuth_deg,
                    latitude = excluded.latitude,
                    longitude = excluded.longitude,
                    location_id = excluded.location_id
                """,
                (
                    row["site_id"],
                    row.get("name"),
                    row.get("timezone") or "Asia/Colombo",
                    float(row["system_kw"]),
                    row.get("tilt_deg"),
                    row.get("azimuth_deg"),
                    row.get("latitude"),
                    row.get("longitude"),
                    row.get("location_id"),
                ),
            )
            conn.commit()

    def list_sites(self) -> list[dict]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                select site_id, name, timezone, system_kw, tilt_deg, azimuth_deg,
                       latitude, longitude, location_id
                from sites
                order by site_id
                """
            )
            columns = [item.name for item in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def add_device(self, device_id: str, site_id: str, token: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                insert into devices (device_id, site_id, token_hash)
                values (%s, %s, %s)
                on conflict (device_id) do update set
                    site_id = excluded.site_id,
                    token_hash = excluded.token_hash
                """,
                (device_id, site_id, hash_token(token)),
            )
            conn.commit()

    def site_for_token(self, token: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "select site_id from devices where token_hash = %s",
                (hash_token(token),),
            ).fetchone()
        return None if row is None else row[0]

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
        with self._connect() as conn:
            conn.execute(
                """
                insert into readings (
                    site_id, ts, pv_kw, consumption_kw, import_kw, export_kw,
                    data_label, is_simulated
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (site_id, ts) do update set
                    pv_kw = excluded.pv_kw,
                    consumption_kw = excluded.consumption_kw,
                    import_kw = excluded.import_kw,
                    export_kw = excluded.export_kw,
                    data_label = excluded.data_label,
                    is_simulated = excluded.is_simulated
                """,
                (
                    site_id,
                    to_py(timestamp),
                    pv_kw,
                    consumption_kw,
                    import_kw,
                    export_kw,
                    data_label,
                    bool(is_simulated),
                ),
            )
            conn.commit()

    def readings(self, site_id: str, limit: int = 500) -> list[dict]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                select site_id, ts, pv_kw, consumption_kw, import_kw, export_kw,
                       data_label, is_simulated
                from readings
                where site_id = %s
                order by ts desc
                limit %s
                """,
                (site_id, int(limit)),
            )
            return [_reading(row) for row in cur.fetchall()]

    def all_readings(self) -> list[dict]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                select site_id, ts, pv_kw, consumption_kw, import_kw, export_kw,
                       data_label, is_simulated
                from readings
                order by site_id, ts
                """
            )
            return [_reading(row) for row in cur.fetchall()]

    def record_failure(self, site_id: str, target: str, message: str, *, issued_at=None, model_version=None) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                insert into forecast_runs (site_id, target, issued_at, status, model_version, message)
                values (%s, %s, %s, 'failed', %s, %s)
                returning run_id
                """,
                (
                    site_id,
                    target,
                    None if issued_at is None else to_py(issued_at),
                    model_version,
                    message[:500],
                ),
            ).fetchone()
            conn.commit()
        return int(row[0])

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
        """Insert one successful issue. Older issues are left in place."""
        issued = to_py(issued_at)
        with self._connect() as conn:
            run = conn.execute(
                """
                insert into forecast_runs (site_id, target, issued_at, status, model_version)
                values (%s, %s, %s, 'success', %s)
                returning run_id
                """,
                (site_id, target, issued, model_version),
            ).fetchone()
            run_id = int(run[0])
            conn.execute(
                "delete from forecasts where site_id = %s and target = %s and issued_at = %s",
                (site_id, target, issued),
            )
            for row in rows:
                conn.execute(
                    """
                    insert into forecasts (
                        site_id, target, ts, issued_at, value_kw, model_version,
                        run_id, data_label, is_simulated
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        site_id,
                        target,
                        to_py(row["timestamp"]),
                        issued,
                        float(row["value_kw"]),
                        model_version,
                        run_id,
                        data_label,
                        bool(is_simulated),
                    ),
                )
            conn.commit()
        return run_id

    def latest_run(self, site_id: str, target: str) -> dict | None:
        with self._connect() as conn:
            cur = conn.execute(
                """
                select run_id, site_id, target, issued_at, status, model_version, message, created_at
                from forecast_runs
                where site_id = %s and target = %s
                order by created_at desc, run_id desc
                limit 1
                """,
                (site_id, target),
            )
            row = cur.fetchone()
            if row is None:
                return None
            columns = [item.name for item in cur.description]
        return dict(zip(columns, row))

    def latest_success(self, site_id: str, target: str) -> dict | None:
        with self._connect() as conn:
            cur = conn.execute(
                """
                select run_id, site_id, target, issued_at, status, model_version, message, created_at
                from forecast_runs
                where site_id = %s and target = %s and status = 'success'
                  and exists (
                    select 1 from forecasts
                    where forecasts.run_id = forecast_runs.run_id
                  )
                order by created_at desc, run_id desc
                limit 1
                """,
                (site_id, target),
            )
            row = cur.fetchone()
            if row is None:
                return None
            columns = [item.name for item in cur.description]
            run = dict(zip(columns, row))
            points = conn.execute(
                """
                select ts, value_kw, data_label, is_simulated
                from forecasts
                where run_id = %s
                order by ts
                """,
                (run["run_id"],),
            ).fetchall()
        run["rows"] = [
            {
                "timestamp": item[0],
                "value_kw": item[1],
                "data_label": item[2],
                "is_simulated": item[3],
            }
            for item in points
        ]
        return run


def _reading(row) -> dict:
    return {
        "site_id": row[0],
        "timestamp": parse_time(row[1]),
        "pv_kw": row[2],
        "consumption_kw": row[3],
        "import_kw": row[4],
        "export_kw": row[5],
        "data_label": row[6],
        "is_simulated": row[7],
    }
