"""Typed application configuration loaded from YAML + environment."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class LoggingConfig(BaseModel):
    model_config = {"populate_by_name": True}
    level: str = "INFO"
    json_output: bool = Field(default=True, alias="json")


class VideoConfig(BaseModel):
    decode_fps: float = 15.0
    reconnect_seconds: float = 5.0
    ring_buffer_seconds: float = 20.0


class DetectorConfig(BaseModel):
    backend: str = "synthetic"
    model: str = "yolov8n.pt"
    confidence: float = 0.30
    inference_fps: float = 5.0
    classes: list[str] = Field(default_factory=lambda: ["person", "forklift", "car", "truck"])


class TrackerConfig(BaseModel):
    backend: str = "builtin"
    update_fps: float = 15.0
    max_age_frames: int = 30
    min_hits: int = 3
    iou_threshold: float = 0.3
    max_tracking_gap_seconds: float = 1.5


class EventEngineConfig(BaseModel):
    update_fps: float = 15.0
    default_cooldown_seconds: int = 30


class StorageConfig(BaseModel):
    database_url: str | None = None
    sqlite_path: str = "./data/sentinel.db"
    object_store_local_path: str = "./data/object-store"


class EvaluationConfig(BaseModel):
    temporal_iou_threshold: float = 0.3


class AppConfig(BaseModel):
    environment: str = "development"
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    detector: DetectorConfig = Field(default_factory=DetectorConfig)
    tracker: TrackerConfig = Field(default_factory=TrackerConfig)
    event_engine: EventEngineConfig = Field(default_factory=EventEngineConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)

    def resolved_database_url(self) -> str:
        """Return the DB URL, falling back to SQLite for local development."""
        env_url = os.getenv("DATABASE_URL")
        if self.storage.database_url:
            return self.storage.database_url
        if env_url and not env_url.startswith("postgresql+psycopg://sentinel:sentinel@localhost"):
            return env_url
        path = Path(self.storage.sqlite_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path.as_posix()}"


def load_config(path: str | os.PathLike[str]) -> AppConfig:
    """Load an :class:`AppConfig` from a YAML file."""
    data: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(data)


def default_config() -> AppConfig:
    return AppConfig()
