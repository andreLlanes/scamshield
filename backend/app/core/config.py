"""Central application settings.

Every tunable in ScamShield is declared here once and read through
:func:`get_settings`, so no module ever reaches for ``os.environ`` directly.
Values come from (in order of precedence) real environment variables, the
repo-root ``.env`` file, then the defaults below.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent

TranscriptionBackend = Literal["auto", "faster-whisper", "transformers", "openai-whisper", "stub"]
StorageBackend = Literal["local", "s3"]


class Settings(BaseSettings):
    """Typed configuration for the whole backend."""

    model_config = SettingsConfigDict(
        env_prefix="SCAMSHIELD_",
        env_file=(REPO_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Application ------------------------------------------------------
    app_name: str = "ScamShield"
    environment: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = True
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # ---- Database ---------------------------------------------------------
    database_url: str = "sqlite+aiosqlite:///./var/scamshield.db"
    database_echo: bool = False

    # ---- Object storage ---------------------------------------------------
    storage_backend: StorageBackend = "local"
    storage_local_path: Path = BACKEND_ROOT / "var" / "uploads"
    s3_bucket: str | None = None
    s3_region: str = "ap-southeast-1"
    s3_endpoint_url: str | None = None

    # ---- Agent 1: transcription ------------------------------------------
    transcription_backend: TranscriptionBackend = "auto"
    whisper_model: str = "large-v3"
    whisper_device: Literal["auto", "cpu", "cuda"] = "auto"
    whisper_compute_type: str = "int8"
    whisper_language: str | None = None
    max_upload_mb: int = 50
    allowed_audio_extensions: set[str] = Field(
        default_factory=lambda: {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm", ".mp4", ".aac"}
    )

    # ---- Agent 2: classical ML classifier ---------------------------------
    classifier_model_path: Path = BACKEND_ROOT / "artifacts" / "scam_classifier.joblib"

    # ---- Agent 3: RAG fact verification -----------------------------------
    chroma_path: Path = BACKEND_ROOT / "data" / "chroma"
    chroma_collection: str = "scamshield_kb"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    knowledge_base_path: Path = BACKEND_ROOT / "data" / "knowledge_base"
    rag_top_k: int = 4

    # ---- LLM / CrewAI -----------------------------------------------------
    agents_enabled: bool = True
    llm_model: str = "ollama/llama3.1:8b"
    llm_base_url: str | None = "http://localhost:11434"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2048
    llm_timeout_seconds: int = 180

    # ---- Scoring ----------------------------------------------------------
    weight_classifier: float = 0.40
    weight_social_engineering: float = 0.35
    weight_fact_check: float = 0.25

    # ---- Pipeline ---------------------------------------------------------
    max_concurrent_analyses: int = 2

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept both a JSON array and a plain comma-separated string."""
        if isinstance(value, str) and not value.strip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator(
        "whisper_language", "s3_bucket", "s3_endpoint_url", "llm_base_url", mode="before"
    )
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def scoring_weights(self) -> dict[str, float]:
        """Normalised evidence weights used by the risk scorer."""
        raw = {
            "classifier": self.weight_classifier,
            "social_engineering": self.weight_social_engineering,
            "fact_check": self.weight_fact_check,
        }
        total = sum(raw.values()) or 1.0
        return {key: value / total for key, value in raw.items()}

    def resolve(self, path: Path) -> Path:
        """Resolve a possibly-relative configured path against the backend root."""
        return path if path.is_absolute() else (BACKEND_ROOT / path).resolve()

    def ensure_runtime_dirs(self) -> None:
        """Create the directories the app writes to at runtime."""
        for path in (
            self.resolve(self.storage_local_path),
            self.resolve(self.chroma_path),
            self.resolve(self.classifier_model_path).parent,
            BACKEND_ROOT / "var",
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings singleton (cached; safe to call from anywhere)."""
    return Settings()
