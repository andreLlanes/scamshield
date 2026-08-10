"""Agent 1 — speech to text.

Picks a Whisper runtime, loads it once, and keeps inference off the event loop.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import anyio

from app.core.config import Settings, get_settings
from app.core.exceptions import TranscriptionError
from app.core.logging import get_logger
from app.ml.transcription.base import TranscriptionEngine
from app.ml.transcription.faster_whisper_backend import FasterWhisperEngine
from app.ml.transcription.openai_whisper_backend import OpenAIWhisperEngine
from app.ml.transcription.stub import StubEngine
from app.ml.transcription.transformers_backend import TransformersWhisperEngine
from app.schemas.transcript import Transcript

logger = get_logger(__name__)

# Order matters: this is the preference list used when the backend is "auto".
_ENGINES: dict[str, type[TranscriptionEngine]] = {
    "faster-whisper": FasterWhisperEngine,
    "transformers": TransformersWhisperEngine,
    "openai-whisper": OpenAIWhisperEngine,
    "stub": StubEngine,
}


class TranscriptionService:
    """Facade over the available Whisper runtimes."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._engine: TranscriptionEngine | None = None
        self._lock = anyio.Lock()

    # ---- Engine selection -------------------------------------------------
    def _select_engine(self) -> TranscriptionEngine:
        configured = self._settings.transcription_backend

        if configured != "auto":
            engine = _ENGINES[configured]()
            if not engine.is_available():
                raise TranscriptionError(
                    f"Transcription backend '{configured}' is configured but its package is not "
                    "installed. Install with: pip install -e '.[asr]'"
                )
            return engine

        for name, engine_cls in _ENGINES.items():
            if name == "stub":
                continue
            engine = engine_cls()
            if engine.is_available():
                logger.info("transcription_backend_selected", backend=name, mode="auto")
                return engine

        logger.warning("transcription_backend_selected", backend="stub", mode="auto")
        return StubEngine()

    @property
    def engine(self) -> TranscriptionEngine:
        if self._engine is None:
            self._engine = self._select_engine()
        return self._engine

    def is_ready(self) -> bool:
        """True when a real (non-stub) Whisper runtime is installed."""
        return self.engine.name != "stub"

    def describe(self) -> dict[str, str]:
        return {
            "backend": self.engine.name,
            "model": self._settings.whisper_model,
            "device": self._settings.whisper_device,
        }

    # ---- Inference --------------------------------------------------------
    async def transcribe(self, audio_path: Path, *, language: str | None = None) -> Transcript:
        """Transcribe a recording without blocking the event loop.

        The lock serialises model loading and inference: Whisper weights are
        large and two concurrent loads would double peak memory for no gain.
        """
        if not audio_path.exists():
            raise TranscriptionError(f"Audio file not found: {audio_path}")

        async with self._lock:
            engine = self.engine
            logger.info("transcription_started", backend=engine.name, file=audio_path.name)
            transcript = await anyio.to_thread.run_sync(
                lambda: engine.transcribe(audio_path, language=language)
            )

        if not transcript.text.strip():
            raise TranscriptionError(
                "The recording produced an empty transcript. It may be silent, "
                "corrupted, or in an unsupported format."
            )

        logger.info(
            "transcription_completed",
            backend=engine.name,
            words=transcript.word_count,
            duration=transcript.duration_seconds,
            language=transcript.language,
        )
        return transcript


@lru_cache(maxsize=1)
def get_transcription_service() -> TranscriptionService:
    """Process-wide transcription service (keeps the model loaded between jobs)."""
    return TranscriptionService()
