"""Agent 1 output — the timestamped transcript."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    """A single utterance with its position in the recording."""

    index: int = Field(..., ge=0, description="Zero-based position in the transcript.")
    start: float = Field(..., ge=0, description="Segment start time in seconds.")
    end: float = Field(..., ge=0, description="Segment end time in seconds.")
    text: str = Field(..., description="Transcribed text for this segment.")
    speaker: str | None = Field(
        default=None, description="Speaker tag when diarisation is available."
    )

    @property
    def timestamp(self) -> str:
        """``mm:ss`` label used in the report citations."""
        minutes, seconds = divmod(int(self.start), 60)
        return f"{minutes:02d}:{seconds:02d}"


class Transcript(BaseModel):
    """Full transcription result produced by the speech-to-text agent."""

    text: str = Field(..., description="Whole transcript as a single string.")
    language: str = Field(default="en", description="Detected or forced language code.")
    duration_seconds: float = Field(default=0.0, ge=0)
    segments: list[TranscriptSegment] = Field(default_factory=list)
    model: str = Field(default="unknown", description="Model that produced the transcript.")
    backend: str = Field(default="unknown", description="Runtime backend used for inference.")

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    def excerpt(self, max_chars: int = 6000) -> str:
        """Trim the transcript so it fits comfortably in an LLM prompt."""
        if len(self.text) <= max_chars:
            return self.text
        return self.text[:max_chars].rsplit(" ", 1)[0] + " […]"

    def timestamped_text(self, max_segments: int = 200) -> str:
        """Render segments as ``[mm:ss] text`` lines for prompt grounding."""
        return "\n".join(
            f"[{segment.timestamp}] {segment.text.strip()}"
            for segment in self.segments[:max_segments]
        )

    def locate(self, quote: str) -> TranscriptSegment | None:
        """Find the segment a quoted phrase came from, if any."""
        needle = quote.strip().lower()
        if not needle:
            return None
        for segment in self.segments:
            if needle in segment.text.lower():
                return segment
        # Fall back to a loose token-overlap match for paraphrased quotes.
        tokens = {token for token in needle.split() if len(token) > 3}
        if not tokens:
            return None
        best: tuple[float, TranscriptSegment] | None = None
        for segment in self.segments:
            words = {token for token in segment.text.lower().split() if len(token) > 3}
            if not words:
                continue
            overlap = len(tokens & words) / len(tokens)
            if overlap >= 0.6 and (best is None or overlap > best[0]):
                best = (overlap, segment)
        return best[1] if best else None
