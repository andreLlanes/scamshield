"""AWS S3 storage backend (also works with any S3-compatible endpoint)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import IO, Any

import anyio

from app.core.exceptions import DependencyUnavailableError, NotFoundError
from app.services.storage.base import StorageBackend


class S3Storage(StorageBackend):
    """Uploads recordings to a bucket; downloads them on demand for Whisper."""

    def __init__(
        self, bucket: str, *, region: str = "ap-southeast-1", endpoint_url: str | None = None
    ) -> None:
        try:
            import boto3  # noqa: PLC0415  — optional extra
        except ImportError as exc:  # pragma: no cover - depends on install extras
            raise DependencyUnavailableError(
                "S3 storage requires boto3. Install with: pip install -e '.[aws]'"
            ) from exc

        self._bucket = bucket
        self._client: Any = boto3.client("s3", region_name=region, endpoint_url=endpoint_url)
        self._tmp_dir = Path(tempfile.gettempdir()) / "scamshield-s3"
        self._tmp_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, key: str, stream: IO[bytes]) -> str:
        await anyio.to_thread.run_sync(
            lambda: self._client.upload_fileobj(stream, self._bucket, key)
        )
        return key

    async def local_path(self, key: str) -> Path:
        target = self._tmp_dir / key.replace("/", "_")
        if target.exists():
            return target

        def _download() -> None:
            target.parent.mkdir(parents=True, exist_ok=True)
            self._client.download_file(self._bucket, key, str(target))

        try:
            await anyio.to_thread.run_sync(_download)
        except Exception as exc:  # botocore raises ClientError for 404
            raise NotFoundError(f"Stored file not found in S3: {key}") from exc
        return target

    async def delete(self, key: str) -> None:
        await anyio.to_thread.run_sync(
            lambda: self._client.delete_object(Bucket=self._bucket, Key=key)
        )
        cached = self._tmp_dir / key.replace("/", "_")
        cached.unlink(missing_ok=True)

    async def exists(self, key: str) -> bool:
        def _head() -> bool:
            try:
                self._client.head_object(Bucket=self._bucket, Key=key)
                return True
            except Exception:
                return False

        return await anyio.to_thread.run_sync(_head)
