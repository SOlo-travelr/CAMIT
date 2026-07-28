"""Shared API dependencies: config, database, object store."""

from __future__ import annotations

import os
from functools import lru_cache

from sentinel.config import AppConfig, load_config
from sentinel.storage.database import Database
from sentinel.storage.object_store import LocalObjectStore


@lru_cache
def get_config() -> AppConfig:
    path = os.getenv("SENTINEL_CONFIG", "configs/development.yaml")
    if os.path.exists(path):
        return load_config(path)
    return AppConfig()


@lru_cache
def get_database() -> Database:
    db = Database(get_config().resolved_database_url())
    db.create_all()
    return db


@lru_cache
def get_object_store() -> LocalObjectStore:
    return LocalObjectStore(get_config().storage.object_store_local_path)
