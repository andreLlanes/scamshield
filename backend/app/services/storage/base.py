"""Storage backend contract.

Audio files are written through this interface so the pipeline never cares
whether it is talking to a local disk or to S3.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import IO


class StorageBackend(ABC):
    """Persist and retrieve uploaded recordings."""

    @abstractmethod
    async def save(self, key: str, stream: IO[bytes]) -> str:
        """Write ``stream`` under ``key`` and return the canonical storage key."""

    @abstractmethod
    async def local_path(self, key: str) -> Path:
        """Return a filesystem path for ``key``.

        Remote backends download to a temporary file; the caller must treat the
        result as read-only and may delete it once finished.
        """

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove ``key``. Deleting a missing key is not an error."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """True when ``key`` is present."""
