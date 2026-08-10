"""Speech-to-text backend contract (Agent 1)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.schemas.transcript import Transcript


class TranscriptionEngine(ABC):
    """A concrete Whisper runtime."""

    name: str = "unknown"

    @abstractmethod
    def is_available(self) -> bool:
        """True when the required package is importable on this machine."""

    @abstractmethod
    def load(self) -> None:
        """Load model weights. Called once, lazily, off the event loop."""

    @abstractmethod
    def transcribe(self, audio_path: Path, *, language: str | None = None) -> Transcript:
        """Transcribe ``audio_path`` into timestamped segments."""

    def unload(self) -> None:  # noqa: B027 - optional hook, deliberately not abstract
        """Release model weights.

        Optional: engines that hold no releasable state (the stub) inherit the
        no-op rather than being forced to implement it.
        """
        return None
