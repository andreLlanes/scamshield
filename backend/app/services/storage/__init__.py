"""Pluggable object storage."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.core.exceptions import ScamShieldError
from app.services.storage.base import StorageBackend
from app.services.storage.local import LocalStorage

__all__ = ["StorageBackend", "LocalStorage", "get_storage"]


def build_storage(settings: Settings) -> StorageBackend:
    """Instantiate the backend named in configuration."""
    if settings.storage_backend == "local":
        return LocalStorage(settings.resolve(settings.storage_local_path))

    if settings.storage_backend == "s3":
        if not settings.s3_bucket:
            raise ScamShieldError("SCAMSHIELD_S3_BUCKET must be set when using the s3 backend.")
        from app.services.storage.s3 import S3Storage  # noqa: PLC0415  — optional extra

        return S3Storage(
            settings.s3_bucket,
            region=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url,
        )

    raise ScamShieldError(f"Unknown storage backend: {settings.storage_backend}")


@lru_cache(maxsize=1)
def get_storage() -> StorageBackend:
    """Process-wide storage singleton."""
    return build_storage(get_settings())
