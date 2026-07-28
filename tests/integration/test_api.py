"""Integration tests for the FastAPI application using an isolated SQLite DB."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Point the app at an isolated SQLite DB + object store for the test.
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "environment: test\n"
        "storage:\n"
        f"  sqlite_path: {(tmp_path / 'test.db').as_posix()}\n"
        f"  object_store_local_path: {(tmp_path / 'store').as_posix()}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SENTINEL_CONFIG", str(cfg))
    monkeypatch.delenv("DATABASE_URL", raising=False)

    import apps.api.dependencies as deps

    deps.get_config.cache_clear()
    deps.get_database.cache_clear()
    deps.get_object_store.cache_clear()

    from apps.api.main import app

    with TestClient(app) as c:
        yield c


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["services"]["database"] == "ok"


def test_camera_zone_policy_flow(client):
    assert client.post(
        "/cameras",
        json={"camera_id": "cam1", "name": "Cam 1", "source_kind": "file", "source_uri": "x.mp4"},
    ).status_code == 200
    assert client.post(
        "/zones", json={"zone_id": "z1", "camera_id": "cam1", "polygon": [[0, 0], [1, 0], [1, 1]]}
    ).status_code == 200

    policy = {
        "policy_id": "p1",
        "name": "restricted",
        "scope": {"camera_ids": ["cam1"]},
        "subjects": {"primary": {"class": "person"}},
        "zones": {"include": ["z1"]},
        "conditions": {"all": [{"type": "zone_entry", "subject": "primary"}]},
        "event": {"type": "restricted_zone", "confidence_threshold": 0.4},
    }
    r = client.post("/policies", json=policy)
    assert r.status_code == 200
    assert r.json()["outcome"] == "Policy accepted"
    assert any(p["policy_id"] == "p1" for p in client.get("/policies").json())


def test_policy_rejects_unknown_camera(client):
    policy = {
        "policy_id": "p2",
        "name": "bad",
        "scope": {"camera_ids": ["ghost"]},
        "subjects": {"primary": {"class": "person"}},
        "zones": {"include": []},
        "conditions": {"all": [{"type": "zone_entry", "subject": "primary"}]},
        "event": {"type": "restricted_zone", "confidence_threshold": 0.4},
    }
    # No cameras registered -> empty context accepts anything; register one to enforce.
    client.post(
        "/cameras",
        json={"camera_id": "cam1", "name": "Cam 1", "source_kind": "file", "source_uri": "x.mp4"},
    )
    r = client.post("/policies/validate", json=policy)
    assert r.json()["outcome"] == "Policy rejected"


def test_incidents_empty_initially(client):
    r = client.get("/incidents")
    assert r.status_code == 200
    assert r.json() == []
