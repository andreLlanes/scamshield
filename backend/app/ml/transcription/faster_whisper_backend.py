"""Whisper large-v3 via CTranslate2 (``faster-whisper``).

This is the preferred runtime: 4-8x faster than the reference implementation
and it runs large-v3 on CPU with int8 quantisation, which matters because the
project brief calls for local inference without API costs.
"""

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


class FasterWhisperEngine(TranscriptionEngine):
    name = "faster-whisper"

    def __init__(self) -> None:
        self._model: Any = None
        self._settings = get_settings()

    def is_available(self) -> bool:
        return importlib.util.find_spec("faster_whisper") is not None

    def _resolve_device(self) -> tuple[str, str]:
        """Pick device/compute type, preferring CUDA when it is actually usable."""
        device = self._settings.whisper_device
        compute_type = self._settings.whisper_compute_type
        if device == "auto":
            try:
                import torch  # noqa: PLC0415  — optional, only used for detection

                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"
        if device == "cuda" and compute_type == "int8":
            compute_type = "float16"
        return device, compute_type

    def load(self) -> None:
        if self._model is not None:
            return
        from faster_whisper import WhisperModel  # noqa: PLC0415  — optional extra

        device, compute_type = self._resolve_device()
        logger.info(
            "whisper_loading",
            backend=self.name,
            model=self._settings.whisper_model,
            device=device,
            compute_type=compute_type,
        )
        self._model = WhisperModel(
            self._settings.whisper_model, device=device, compute_type=compute_type
        )

    def transcribe(self, audio_path: Path, *, language: str | None = None) -> Transcript:
        self.load()
        assert self._model is not None

        try:
            segments_iter, info = self._model.transcribe(
                str(audio_path),
                language=language or self._settings.whisper_language,
                beam_size=5,
                vad_filter=True,
                word_timestamps=False,
                condition_on_previous_text=False,
            )
        except Exception as exc:
            raise TranscriptionError(f"faster-whisper failed: {exc}") from exc

        segments = [
            TranscriptSegment(
                index=index,
                start=float(segment.start or 0.0),
                end=float(segment.end or 0.0),
                text=segment.text.strip(),
            )
            for index, segment in enumerate(segments_iter)
            if segment.text and segment.text.strip()
        ]

        return Transcript(
            text=" ".join(segment.text for segment in segments).strip(),
            language=getattr(info, "language", None) or language or "en",
            duration_seconds=float(getattr(info, "duration", 0.0) or 0.0),
            segments=segments,
            model=self._settings.whisper_model,
            backend=self.name,
        )

    def unload(self) -> None:
        self._model = None
