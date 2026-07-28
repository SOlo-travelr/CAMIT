"""Object storage abstraction with a local-filesystem default.

An S3/MinIO-backed implementation can be dropped in behind the same interface.
URIs use the ``object://<bucket>/<key>`` scheme.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol


class ObjectStore(Protocol):
    def put(self, key: str, source_path: str | Path) -> str:
        ...

    def uri_to_path(self, uri: str) -> Path | None:
        ...


class LocalObjectStore:
    def __init__(self, root: str | Path, bucket: str = "sentinel") -> None:
        self.root = Path(root)
        self.bucket = bucket
        (self.root / bucket).mkdir(parents=True, exist_ok=True)

    def put(self, key: str, source_path: str | Path) -> str:
        dest = self.root / self.bucket / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest)
        return f"object://{self.bucket}/{key}"

    def write_bytes(self, key: str, data: bytes) -> str:
        dest = self.root / self.bucket / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return f"object://{self.bucket}/{key}"

    def uri_to_path(self, uri: str) -> Path | None:
        prefix = "object://"
        if not uri.startswith(prefix):
            return None
        rel = uri[len(prefix) :]
        return self.root / rel
