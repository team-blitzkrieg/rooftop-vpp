"""Postgres store. Imported only when DATABASE_URL is set, so tests need no database."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from api.util import hash_key, parse_time

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class PostgresStore:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def _connect(self):
        import psycopg

        return psycopg.connect(self.database_url)

    def apply_schema(self) -> None:
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.execute(sql)
            conn.commit()

    def add_site(self, site_id: str, **fields) -> None:
        columns = ["site_id", *fields.keys()]
        values = [site_id, *fields.values()]
        assignments = ", ".join(f"{name} = excluded.{name}" for name in fields)
        placeholders = ", ".join(["%s"] * len(values))
        sql = (
            f"insert into sites ({', '.join(columns)}) values ({placeholders}) "
            f"on conflict (site_id) do update set {assignments or 'site_id = excluded.site_id'}"
        )
        with self._connect() as conn:
            conn.execute(sql, values)
            conn.commit()

    def add_device(self, device_id: str, site_id: str, raw_key: str) -> None:
        if site_id:
            with self._connect() as conn:
                conn.execute(
                    "insert into sites (site_id) values (%s) on conflict (site_id) do nothing",
                    (site_id,),
                )
                conn.execute(
                    """
                    insert into devices (device_id, site_id, key_sha256)
                    values (%s, %s, %s)
                    on conflict (device_id) do update set
                        site_id = excluded.site_id,
                        key_sha256 = excluded.key_sha256
                    """,
                    (device_id, site_id, hash_key(raw_key)),
                )
                conn.commit()

    def site_for_key(self, raw_key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "select site_id from devices where key_sha256 = %s",
                (hash_key(raw_key),),
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
        stamp = parse_time(timestamp).to_pydatetime()
        with self._connect() as conn:
            conn.execute(
                """
                insert into readings (
                    site_id, timestamp, pv_kw, consumption_kw, import_kw, export_kw,
                    data_label, is_simulated
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (site_id, timestamp) do update set
                    pv_kw = excluded.pv_kw,
                    consumption_kw = excluded.consumption_kw,
                    import_kw = excluded.import_kw,
                    export_kw = excluded.export_kw,
                    data_label = excluded.data_label,
                    is_simulated = excluded.is_simulated
                """,
                (
                    site_id,
                    stamp,
                    pv_kw,
                    consumption_kw,
                    import_kw,
                    export_kw,
                    data_label,
                    bool(is_simulated),
                ),
            )
            conn.commit()

    def reading_count(self, site_id: str | None = None) -> int:
        with self._connect() as conn:
            if site_id is None:
                row = conn.execute("select count(*) from readings").fetchone()
            else:
                row = conn.execute(
                    "select count(*) from readings where site_id = %s",
                    (site_id,),
                ).fetchone()
        return int(row[0])

    def list_sites(self) -> list[dict]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                select site_id, name, timezone, system_kw, tilt_deg, azimuth_deg,
                       latitude, longitude, has_meter, demand_scale_kw
                from sites
                order by site_id
                """
            )
            columns = [item.name for item in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def readings_for(self, site_id: str, *, include_simulated: bool) -> list[dict]:
        sql = """
            select site_id, timestamp, pv_kw, consumption_kw, import_kw, export_kw,
                   data_label, is_simulated
            from readings
            where site_id = %s
        """
        params: list = [site_id]
        if not include_simulated:
            sql += " and is_simulated = false"
        sql += " order by timestamp"
        with self._connect() as conn:
            cur = conn.execute(sql, params)
            columns = [item.name for item in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
        for row in rows:
            row["timestamp"] = parse_time(row["timestamp"])
        return rows

    def issue_day_count(self, *, include_simulated: bool) -> int:
        sql = "select count(distinct (timestamp at time zone 'Asia/Colombo')::date) from readings"
        if not include_simulated:
            sql += " where is_simulated = false"
        with self._connect() as conn:
            row = conn.execute(sql).fetchone()
        return int(row[0])

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
        issued = None if issued_at is None else parse_time(issued_at).to_pydatetime()
        with self._connect() as conn:
            row = conn.execute(
                """
                insert into forecast_runs (site_id, target, issued_at, status, model_version, message)
                values (%s, %s, %s, %s, %s, %s)
                returning run_id
                """,
                (site_id, target, issued, status, model_version, message),
            ).fetchone()
            conn.commit()
        return int(row[0])

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
        issued = parse_time(issued_at).to_pydatetime()
        with self._connect() as conn:
            conn.execute(
                """
                delete from forecasts
                where site_id = %s and target = %s and issued_at = %s
                """,
                (site_id, target, issued),
            )
            for row in rows:
                conn.execute(
                    """
                    insert into forecasts (
                        site_id, target, timestamp, issued_at, lead_hours, value_kw,
                        baseline_kw, net_kw, model_version, run_id, resolution,
                        data_label, is_simulated
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        site_id,
                        target,
                        parse_time(row["timestamp"]).to_pydatetime(),
                        issued,
                        row.get("lead_hours"),
                        float(row["value_kw"]),
                        row.get("baseline_kw"),
                        row.get("net_kw"),
                        model_version,
                        run_id,
                        resolution,
                        data_label,
                        bool(is_simulated),
                    ),
                )
            conn.commit()

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
                select timestamp, issued_at, lead_hours, value_kw, baseline_kw, net_kw,
                       model_version, data_label, is_simulated, resolution
                from forecasts
                where site_id = %s and target = %s and issued_at = %s and run_id = %s
                order by timestamp
                """,
                (site_id, target, run["issued_at"], run["run_id"]),
            ).fetchall()
        run["rows"] = [
            {
                "timestamp": item[0],
                "issued_at": item[1],
                "lead_hours": item[2],
                "value_kw": item[3],
                "baseline_kw": item[4],
                "net_kw": item[5],
                "model_version": item[6],
                "data_label": item[7],
                "is_simulated": item[8],
                "resolution": item[9],
            }
            for item in points
        ]
        return run

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
        import json

        payload = None if metrics is None else json.dumps(metrics)
        with self._connect() as conn:
            if promoted:
                conn.execute(
                    "update model_versions set promoted = false where target = %s and promoted",
                    (target,),
                )
            conn.execute(
                """
                insert into model_versions (version, target, metrics, promoted, artefact_url, git_sha)
                values (%s, %s, %s::jsonb, %s, %s, %s)
                on conflict (version) do update set
                    target = excluded.target,
                    metrics = excluded.metrics,
                    promoted = excluded.promoted,
                    artefact_url = excluded.artefact_url,
                    git_sha = excluded.git_sha
                """,
                (version, target, payload, bool(promoted), artefact_url, git_sha),
            )
            conn.commit()

    def promoted_model(self, target: str) -> dict | None:
        with self._connect() as conn:
            cur = conn.execute(
                """
                select version, target, metrics, promoted, artefact_url, git_sha, created_at
                from model_versions
                where target = %s and promoted
                """,
                (target,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            columns = [item.name for item in cur.description]
        return dict(zip(columns, row))

    def prune(self, *, now=None, reading_days: int = 90, forecast_days: int = 30) -> None:
        moment = now or datetime.now(timezone.utc)
        reading_cut = moment - timedelta(days=reading_days)
        forecast_cut = moment - timedelta(days=forecast_days)
        with self._connect() as conn:
            conn.execute("delete from readings where timestamp < %s", (reading_cut,))
            conn.execute(
                """
                delete from forecasts as forecast
                where forecast.timestamp < %s
                  and not exists (
                    select 1
                    from forecast_runs as run
                    where run.status = 'success'
                      and run.site_id = forecast.site_id
                      and run.target = forecast.target
                      and run.issued_at = forecast.issued_at
                      and run.run_id = (
                        select newer.run_id
                        from forecast_runs as newer
                        where newer.site_id = forecast.site_id
                          and newer.target = forecast.target
                          and newer.status = 'success'
                        order by newer.created_at desc, newer.run_id desc
                        limit 1
                      )
                  )
                """,
                (forecast_cut,),
            )
            conn.commit()
