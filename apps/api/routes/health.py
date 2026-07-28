"""Health and metrics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text

from apps.api.dependencies import get_database
from sentinel.observability.metrics import metrics_available, render_metrics
from sentinel.storage.database import Database

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Database = Depends(get_database)) -> dict:
    services = {"api": "ok"}
    try:
        with db.session() as session:
            session.execute(text("SELECT 1"))
        services["database"] = "ok"
    except Exception as exc:  # surface failures, never hide them
        services["database"] = f"error: {exc}"
    status = "healthy" if all(v == "ok" for v in services.values()) else "degraded"
    return {"status": status, "services": services}


@router.get("/metrics")
def metrics() -> Response:
    if not metrics_available():
        return Response(
            "# prometheus_client not installed\n", media_type="text/plain"
        )
    return Response(render_metrics(), media_type="text/plain; version=0.0.4")
