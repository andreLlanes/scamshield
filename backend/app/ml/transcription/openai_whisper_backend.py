"""Whisper via OpenAI's reference ``whisper`` package (local inference)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.exceptions import TranscriptionError
from app.core.logging import get_logger
from app.ml.transcription.base import TranscriptionEngine
from app.schemas.transcript import Transcript, TranscriptSegment

logger = get_logger(__name__)


class OpenAIWhisperEngine(TranscriptionEngine):
    name = "openai-whisper"

    def __init__(self) -> None:
        self._model: Any = None
        self._settings = get_settings()

    def is_available(self) -> bool:
        return importlib.util.find_spec("whisper") is not None

    def load(self) -> None:
        if self._model is not None:
            return
        import whisper  # noqa: PLC0415  — optional extra

        logger.info("whisper_loading", backend=self.name, model=self._settings.whisper_model)
        self._model = whisper.load_model(self._settings.whisper_model)

    def transcribe(self, audio_path: Path, *, language: str | None = None) -> Transcript:
        self.load()
        assert self._model is not None

        try:
            result = self._model.transcribe(
                str(audio_path),
                language=language or self._settings.whisper_language,
                verbose=False,
            )
        except Exception as exc:
            raise TranscriptionError(f"openai-whisper failed: {exc}") from exc

        segments = [
            TranscriptSegment(
                index=index,
                start=float(segment.get("start", 0.0)),
                end=float(segment.get("end", 0.0)),
                text=str(segment.get("text", "")).strip(),
            )
            for index, segment in enumerate(result.get("segments") or [])
            if str(segment.get("text", "")).strip()
        ]

        return Transcript(
            text=str(result.get("text", "")).strip(),
            language=str(result.get("language") or language or "en"),
            duration_seconds=segments[-1].end if segments else 0.0,
            segments=segments,
            model=self._settings.whisper_model,
            backend=self.name,
        )

    def unload(self) -> None:
        self._model = None
