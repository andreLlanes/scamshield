"""Filesystem storage backend — the default for local development."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import IO

import anyio

from app.core.exceptions import NotFoundError
from app.services.storage.base import StorageBackend


class LocalStorage(StorageBackend):
    """Stores uploads under a single root directory."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        target = (self._root / key).resolve()
        # Guard against ``..`` traversal in a caller-supplied key.
        if not target.is_relative_to(self._root.resolve()):
            raise ValueError(f"Storage key escapes the storage root: {key!r}")
        return target

    async def save(self, key: str, stream: IO[bytes]) -> str:
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)

        def _write() -> None:
            with target.open("wb") as handle:
                shutil.copyfileobj(stream, handle, length=1024 * 1024)

        await anyio.to_thread.run_sync(_write)
        return key

    async def local_path(self, key: str) -> Path:
        target = self._resolve(key)
        if not target.exists():
            raise NotFoundError(f"Stored file not found: {key}")
        return target

    async def delete(self, key: str) -> None:
        target = self._resolve(key)
        await anyio.to_thread.run_sync(lambda: target.unlink(missing_ok=True))

    async def exists(self, key: str) -> bool:
        return self._resolve(key).exists()
