"""bge-small sentence embeddings for the vector store."""

from __future__ import annotations

import importlib.util
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# bge models are trained with an asymmetric query prefix; skipping it measurably
# hurts retrieval, so it is applied here rather than left to callers.
_BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class EmbeddingModel:
    """Lazily loaded sentence-transformers encoder."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._model: Any = None

    @property
    def name(self) -> str:
        return self._settings.embedding_model

    def is_available(self) -> bool:
        return importlib.util.find_spec("sentence_transformers") is not None

    def load(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415  — optional extra

        logger.info("embedding_model_loading", model=self.name)
        self._model = SentenceTransformer(self.name)

    def _prefix(self, text: str, *, is_query: bool) -> str:
        if is_query and "bge" in self.name.lower():
            return _BGE_QUERY_PREFIX + text
        return text

    def encode(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        self.load()
        assert self._model is not None
        prepared = [self._prefix(text, is_query=is_query) for text in texts]
        vectors = self._model.encode(prepared, normalize_embeddings=True, show_progress_bar=False)
        return [vector.tolist() for vector in vectors]
