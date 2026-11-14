"""Forecast API. Poll it, or listen on the SSE stream. No inverter commands."""

from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from serve.clock import parse_time
from serve.jobs import run_forecast, run_retrain
from serve.log import configure_logging
from serve.settings import load_settings
from serve.tokens import keys_match

logger = logging.getLogger(__name__)


class ReadingIn(BaseModel):
    timestamp: str
    pv_kw: float | None = None
    consumption_kw: float | None = None
    import_kw: float | None = None
    export_kw: float | None = None


def create_app(store=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging()
        if app.state.store is None:
            from serve.db import PostgresStore

            settings = load_settings()
            app.state.store = PostgresStore(settings.database_url)
            app.state.store.migrate()
            logger.info("Database ready")
        yield

    app = FastAPI(
        title="Rooftops to Power Plant",
        description="Read-only PV, demand and net-load forecasts. This service does not command inverters.",
        lifespan=lifespan,
    )
    app.state.store = store
    settings = load_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins or ["http://localhost:8000"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    def current_store():
        if app.state.store is None:
            raise HTTPException(status_code=503, detail="Store is not ready")
        return app.state.store

    def require_api_key(
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
    ) -> None:
        expected = load_settings().api_key
        if not expected:
            return
        presented = x_api_key
        if presented is None and authorization and authorization.lower().startswith("bearer "):
            presented = authorization.split(" ", 1)[1]
        if presented is None or not keys_match(presented, expected):
            raise HTTPException(status_code=401, detail="API key is required")

    def require_admin(x_admin_key: str | None = Header(default=None)) -> None:
        expected = load_settings().admin_api_key
        if not expected:
            raise HTTPException(status_code=503, detail="ADMIN_API_KEY is not configured")
        if x_admin_key is None or not keys_match(x_admin_key, expected):
            raise HTTPException(status_code=401, detail="X-Admin-Key is required")

    @app.get("/health")
    def health(store=Depends(current_store)):
        database = "ok" if store.ping() else "down"
        body = {"status": "ok" if database == "ok" else "degraded", "database": database, "controls_equipment": False}
        if database != "ok":
            raise HTTPException(status_code=503, detail=body)
        return body

    @app.get("/sites")
    def sites(_: None = Depends(require_api_key), store=Depends(current_store)):
        return {"controls_equipment": False, "sites": store.list_sites()}

    @app.get("/readings/{site_id}")
    def readings(
        site_id: str,
        limit: int = Query(default=168, ge=1, le=5000),
        _: None = Depends(require_api_key),
        store=Depends(current_store),
    ):
        rows = []
        for row in store.readings(site_id, limit=limit):
            rows.append(
                {
                    "timestamp": parse_time(row["timestamp"]).isoformat(),
                    "pv_kw": row.get("pv_kw"),
                    "consumption_kw": row.get("consumption_kw"),
                    "data_label": row.get("data_label"),
                    "is_simulated": bool(row.get("is_simulated")),
                }
            )
        return {"site_id": site_id, "controls_equipment": False, "rows": rows}

    @app.get("/forecast/{site_id}")
    def forecast(
        site_id: str,
        target: str = Query(default="pv", pattern="^(pv|demand|net)$"),
        _: None = Depends(require_api_key),
        store=Depends(current_store),
    ):
        return _forecast_body(store, site_id, target)

    @app.get("/forecast/{site_id}/events")
    def forecast_events(
        site_id: str,
        target: str = Query(default="pv", pattern="^(pv|demand|net)$"),
        once: int = Query(default=0, ge=0, le=1),
        _: None = Depends(require_api_key),
        store=Depends(current_store),
    ):
        def stream():
            previous = None
            while True:
                payload = _forecast_body(store, site_id, target, missing_ok=True)
                encoded = json.dumps(payload)
                if encoded != previous:
                    yield f"data: {encoded}\n\n"
                    previous = encoded
                if once:
                    break
                time.sleep(5)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.post("/ingest")
    def ingest(
        body: ReadingIn,
        x_device_token: str | None = Header(default=None),
        store=Depends(current_store),
    ):
        if not x_device_token:
            raise HTTPException(status_code=401, detail="X-Device-Token is required")
        site_id = store.site_for_token(x_device_token)
        if site_id is None:
            raise HTTPException(status_code=401, detail="Unknown device token")
        values = body.model_dump()
        powers = {key: values[key] for key in ("pv_kw", "consumption_kw", "import_kw", "export_kw")}
        if all(value is None for value in powers.values()):
            raise HTTPException(status_code=422, detail="Send at least one power field")
        for name, value in powers.items():
            if value is not None and value < 0:
                raise HTTPException(status_code=422, detail=f"{name} cannot be negative")
        store.upsert_reading(site_id, body.timestamp, **powers)
        logger.info("Ingest %s %s", site_id, body.timestamp)
        return {"site_id": site_id, "stored": True, "controls_equipment": False}

    @app.post("/jobs/forecast")
    def job_forecast(_: None = Depends(require_admin), store=Depends(current_store)):
        return run_forecast(store)

    @app.post("/jobs/retrain")
    def job_retrain(_: None = Depends(require_admin), store=Depends(current_store)):
        return run_retrain(store)

    return app


def _forecast_body(store, site_id: str, target: str, *, missing_ok: bool = False) -> dict:
    success = store.latest_success(site_id, target)
    if success is None or not success.get("rows"):
        if missing_ok:
            return {
                "site_id": site_id,
                "target": target,
                "stale": True,
                "using_previous": False,
                "controls_equipment": False,
                "rows": [],
            }
        raise HTTPException(status_code=404, detail="No forecast yet")
    latest = store.latest_run(site_id, target)
    using_previous = bool(
        latest
        and latest["status"] == "failed"
        and latest["run_id"] != success["run_id"]
    )
    issued = parse_time(success["issued_at"])
    stale_after = timedelta(minutes=load_settings().stale_after_minutes)
    stale = datetime.now(timezone.utc) - issued.to_pydatetime() > stale_after
    sample = success["rows"][0]
    return {
        "site_id": site_id,
        "target": target,
        "issued_at": issued.isoformat(),
        "model_version": success.get("model_version"),
        "stale": stale,
        "using_previous": using_previous,
        "controls_equipment": False,
        "data_label": sample.get("data_label"),
        "message": latest.get("message") if using_previous and latest else None,
        "rows": [
            {
                "timestamp": parse_time(row["timestamp"]).isoformat(),
                "value_kw": row["value_kw"],
            }
            for row in success["rows"]
        ],
    }


app = create_app()
