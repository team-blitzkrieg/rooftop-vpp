"""Forecast API. Poll it. It does not open a socket to an inverter.

Cold starts are expected on the free hosts. If this process is asleep, the
front end can read the `forecasts` table from Supabase with the anon key.
"""

from __future__ import annotations

import hmac
import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from api.memory import MemoryStore
from api.util import parse_time

STALE_AFTER = timedelta(hours=26)


class ReadingIn(BaseModel):
    timestamp: str
    pv_kw: float | None = None
    consumption_kw: float | None = None
    import_kw: float | None = None
    export_kw: float | None = None

    def powers(self) -> dict[str, float | None]:
        return {
            "pv_kw": self.pv_kw,
            "consumption_kw": self.consumption_kw,
            "import_kw": self.import_kw,
            "export_kw": self.export_kw,
        }


class ModelIn(BaseModel):
    version: str
    target: str = Field(pattern="^(pv|demand)$")
    metrics: dict | None = None
    artefact_url: str | None = None
    git_sha: str | None = None
    mae_kw: float | None = None


def create_app(store=None) -> FastAPI:
    app = FastAPI(
        title="Rooftops to Power Plant",
        description=(
            "Read-only PV and household demand forecasts. "
            "This service does not command inverters."
        ),
    )
    app.state.store = store if store is not None else default_store()

    def store_dep():
        return app.state.store

    def require_read(x_read_key: str | None = Header(default=None)) -> None:
        expected = os.environ.get("READ_API_KEY", "")
        if not expected:
            return
        if x_read_key is None or not hmac.compare_digest(x_read_key, expected):
            raise HTTPException(status_code=401, detail="X-Read-Key is required")

    def require_admin(x_admin_key: str | None = Header(default=None)) -> None:
        expected = os.environ.get("ADMIN_API_KEY", "")
        if not expected:
            raise HTTPException(status_code=503, detail="ADMIN_API_KEY is not configured")
        if x_admin_key is None or not hmac.compare_digest(x_admin_key, expected):
            raise HTTPException(status_code=401, detail="X-Admin-Key is required")

    @app.get("/health")
    def health():
        return {"status": "ok", "controls_equipment": False, "timezone": "Asia/Colombo"}

    @app.post("/ingest")
    def ingest(body: ReadingIn, x_device_key: str | None = Header(default=None), store=Depends(store_dep)):
        if not x_device_key:
            raise HTTPException(status_code=401, detail="X-Device-Key is required")
        site_id = store.site_for_key(x_device_key)
        if site_id is None:
            raise HTTPException(status_code=401, detail="Unknown device key")
        values = body.powers()
        if all(value is None for value in values.values()):
            raise HTTPException(status_code=422, detail="Send at least one power field")
        for name, value in values.items():
            if value is not None and value < 0:
                raise HTTPException(status_code=422, detail=f"{name} cannot be negative")
        store.upsert_reading(site_id, body.timestamp, **values)
        return {"site_id": site_id, "stored": True, "controls_equipment": False}

    @app.get("/forecasts/{site_id}")
    def forecasts(
        site_id: str,
        target: str = "pv",
        store=Depends(store_dep),
        _: None = Depends(require_read),
    ):
        if target not in {"pv", "demand"}:
            raise HTTPException(status_code=422, detail="target must be pv or demand")
        success = store.latest_success(site_id, target)
        if success is None or not success["rows"]:
            raise HTTPException(status_code=404, detail="No forecast yet")
        latest = store.latest_run(site_id, target)
        using_previous = bool(
            latest
            and latest["status"] == "failed"
            and latest["created_at"] >= success["created_at"]
            and latest["run_id"] != success["run_id"]
        )
        issued = parse_time(success["issued_at"])
        stale = datetime.now(timezone.utc) - issued.to_pydatetime() > STALE_AFTER
        label = success["rows"][0].get("data_label") or "SIMULATED"
        return {
            "site_id": site_id,
            "target": target,
            "issued_at": issued.isoformat(),
            "stale": stale,
            "using_previous": using_previous,
            "controls_equipment": False,
            "data_label": label,
            "model_version": success.get("model_version"),
            "message": latest.get("message") if using_previous and latest else None,
            "rows": [_public_row(row) for row in success["rows"]],
        }

    @app.post("/models")
    def register_model(body: ModelIn, store=Depends(store_dep), _: None = Depends(require_admin)):
        from api.util import should_promote, test_mae

        current = store.promoted_model(body.target)
        current_mae = test_mae(current["metrics"]) if current else None
        new_mae = body.mae_kw if body.mae_kw is not None else test_mae(body.metrics)
        promoted = should_promote(new_mae, current_mae)
        store.insert_model(
            body.version,
            body.target,
            body.metrics,
            promoted=promoted,
            artefact_url=body.artefact_url,
            git_sha=body.git_sha,
        )
        return {"version": body.version, "promoted": promoted, "controls_equipment": False}

    return app


def _public_row(row: dict) -> dict:
    stamp = row["timestamp"]
    text = stamp.isoformat() if hasattr(stamp, "isoformat") else str(stamp)
    return {
        "timestamp": text,
        "value_kw": row["value_kw"],
        "baseline_kw": row.get("baseline_kw"),
        "net_kw": row.get("net_kw"),
    }


def default_store():
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return MemoryStore()
    from api.postgres import PostgresStore

    return PostgresStore(url)


app = create_app()
