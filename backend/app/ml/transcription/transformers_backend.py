"""Whisper large-v3 via the Hugging Face ``transformers`` ASR pipeline.

Kept as an alternative to faster-whisper for environments that already carry a
torch install (a GPU box, or Colab) and would rather not add CTranslate2.
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

_MODEL_IDS = {
    "large-v3": "openai/whisper-large-v3",
    "large-v3-turbo": "openai/whisper-large-v3-turbo",
    "medium": "openai/whisper-medium",
    "small": "openai/whisper-small",
    "base": "openai/whisper-base",
    "tiny": "openai/whisper-tiny",
}


class TransformersWhisperEngine(TranscriptionEngine):
    name = "transformers"

    def __init__(self) -> None:
        self._pipeline: Any = None
        self._settings = get_settings()

    def is_available(self) -> bool:
        return (
            importlib.util.find_spec("transformers") is not None
            and importlib.util.find_spec("torch") is not None
        )

    @property
    def _model_id(self) -> str:
        configured = self._settings.whisper_model
        return _MODEL_IDS.get(configured, configured)

    def load(self) -> None:
        if self._pipeline is not None:
            return
        import torch  # noqa: PLC0415
        from transformers import pipeline  # noqa: PLC0415

        device = self._settings.whisper_device
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32

        logger.info("whisper_loading", backend=self.name, model=self._model_id, device=device)
        self._pipeline = pipeline(
            "automatic-speech-recognition",
            model=self._model_id,
            torch_dtype=dtype,
            device=device,
            chunk_length_s=30,
            return_timestamps=True,
        )

    def transcribe(self, audio_path: Path, *, language: str | None = None) -> Transcript:
        self.load()
        assert self._pipeline is not None

        generate_kwargs: dict[str, Any] = {}
        target_language = language or self._settings.whisper_language
        if target_language:
            generate_kwargs["language"] = target_language

        try:
            result = self._pipeline(str(audio_path), generate_kwargs=generate_kwargs or None)
        except Exception as exc:
            raise TranscriptionError(f"transformers Whisper failed: {exc}") from exc

        segments: list[TranscriptSegment] = []
        for index, chunk in enumerate(result.get("chunks") or []):
            text = (chunk.get("text") or "").strip()
            if not text:
                continue
            start, end = chunk.get("timestamp") or (0.0, 0.0)
            segments.append(
                TranscriptSegment(
                    index=index,
                    start=float(start or 0.0),
                    end=float(end or start or 0.0),
                    text=text,
                )
            )

        full_text = (result.get("text") or "").strip()
        if not segments and full_text:
            segments = [TranscriptSegment(index=0, start=0.0, end=0.0, text=full_text)]

        return Transcript(
            text=full_text or " ".join(segment.text for segment in segments),
            language=target_language or "en",
            duration_seconds=segments[-1].end if segments else 0.0,
            segments=segments,
            model=self._model_id,
            backend=self.name,
        )

    def unload(self) -> None:
        self._pipeline = None
