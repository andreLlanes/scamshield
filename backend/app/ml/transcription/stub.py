"""Deterministic stand-in engine used by tests and offline demos.

It never invents speech. It only reads a sidecar transcript placed next to the
audio file (``call.mp3`` -> ``call.mp3.txt`` or ``call.txt``); with no sidecar
it fails loudly rather than fabricating a transcript, because a made-up
transcript would silently poison every downstream agent.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.exceptions import TranscriptionError
from app.ml.transcription.base import TranscriptionEngine
from app.schemas.transcript import Transcript, TranscriptSegment

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_SECONDS_PER_WORD = 0.45


def transcript_from_text(
    text: str, *, language: str = "en", model: str = "stub", backend: str = "stub"
) -> Transcript:
    """Turn raw text into a segmented transcript with synthesised timings.

    Also used by the ``/analyses/text`` endpoint so a pasted transcript flows
    through exactly the same downstream agents as a real recording.
    """
    sentences = [part.strip() for part in _SENTENCE_SPLIT.split(text.strip()) if part.strip()]
    segments: list[TranscriptSegment] = []
    cursor = 0.0
    for index, sentence in enumerate(sentences):
        span = max(len(sentence.split()) * _SECONDS_PER_WORD, 1.0)
        segments.append(
            TranscriptSegment(
                index=index, start=round(cursor, 2), end=round(cursor + span, 2), text=sentence
            )
        )
        cursor += span

    return Transcript(
        text=text.strip(),
        language=language,
        duration_seconds=round(cursor, 2),
        segments=segments,
        model=model,
        backend=backend,
    )


class StubEngine(TranscriptionEngine):
    name = "stub"

    def is_available(self) -> bool:
        return True

    def load(self) -> None:
        return None

    def transcribe(self, audio_path: Path, *, language: str | None = None) -> Transcript:
        for candidate in (
            audio_path.with_suffix(audio_path.suffix + ".txt"),
            audio_path.with_suffix(".txt"),
        ):
            if candidate.exists():
                return transcript_from_text(
                    candidate.read_text(encoding="utf-8"), language=language or "en"
                )

        raise TranscriptionError(
            "The stub transcription backend needs a sidecar .txt next to the audio file. "
            "Install a real engine instead: pip install -e '.[asr]' "
            "(then set SCAMSHIELD_TRANSCRIPTION_BACKEND=faster-whisper), "
            "or submit a transcript directly to POST /api/v1/analyses/text.",
            details={"audio_path": audio_path.name},
        )
