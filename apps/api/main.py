"""FastAPI application entrypoint.

Wires routers for cameras, zones, policies, incidents, feedback and health. The
API never touches the frame-processing loop; it manages configuration and serves
incident evidence.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.api.dependencies import get_config, get_database
from apps.api.routes import cameras, feedback, health, incidents, policies, zones
from sentinel.observability.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = get_config()
    configure_logging(config.logging.level, config.logging.json_output)
    get_database()  # ensure schema exists
    yield


app = FastAPI(title="Sentinel Platform API", version="0.1.0", lifespan=lifespan)

app.include_router(health.router)
app.include_router(cameras.router)
app.include_router(zones.router)
app.include_router(policies.router)
app.include_router(incidents.router)
app.include_router(feedback.router)


@app.get("/")
def root() -> dict:
    return {
        "service": "sentinel-platform",
        "version": "0.1.0",
        "events": ["restricted_zone", "loitering", "proximity", "collision_risk"],
    }
