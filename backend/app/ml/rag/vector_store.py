"""Vector stores backing Agent 3's retrieval step.

Two implementations behind one interface:

* :class:`ChromaVectorStore` — the production path from the design (persistent
  ChromaDB collection + bge-small embeddings).
* :class:`TfidfVectorStore` — an in-memory cosine-similarity index over the
  same chunks, used when chromadb/sentence-transformers are not installed. The
  knowledge base is small enough that this stays a usable fallback rather than
  a stub.
"""

from __future__ import annotations

import importlib.util
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.ml.rag.documents import KnowledgeChunk
from app.ml.rag.embeddings import EmbeddingModel
from app.schemas.factcheck import RetrievedDocument

logger = get_logger(__name__)


class VectorStore(ABC):
    """Store and search knowledge chunks."""

    name: str = "unknown"

    @abstractmethod
    def index(self, chunks: list[KnowledgeChunk]) -> int:
        """Replace the collection contents with ``chunks``; return the count."""

    @abstractmethod
    def search(self, query: str, *, top_k: int = 4) -> list[RetrievedDocument]:
        """Return the ``top_k`` closest chunks to ``query``."""

    @abstractmethod
    def count(self) -> int:
        """Number of indexed chunks."""


class ChromaVectorStore(VectorStore):
    """Persistent ChromaDB collection embedded with bge-small."""

    name = "chromadb"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._embedder = EmbeddingModel(self._settings)
        self._client: Any = None
        self._collection: Any = None

    @staticmethod
    def is_available() -> bool:
        return (
            importlib.util.find_spec("chromadb") is not None
            and importlib.util.find_spec("sentence_transformers") is not None
        )

    def _connect(self) -> Any:
        if self._collection is not None:
            return self._collection
        import chromadb  # noqa: PLC0415  — optional extra
        from chromadb.config import Settings as ChromaSettings  # noqa: PLC0415

        path: Path = self._settings.resolve(self._settings.chroma_path)
        path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(path), settings=ChromaSettings(anonymized_telemetry=False)
        )
        self._collection = self._client.get_or_create_collection(
            name=self._settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )
        return self._collection

    def index(self, chunks: list[KnowledgeChunk]) -> int:
        collection = self._connect()
        assert self._client is not None

        # Recreate rather than upsert: re-seeding must not leave chunks behind
        # from documents that were edited or deleted.
        self._client.delete_collection(self._settings.chroma_collection)
        self._collection = self._client.get_or_create_collection(
            name=self._settings.chroma_collection, metadata={"hnsw:space": "cosine"}
        )
        collection = self._collection

        if not chunks:
            return 0

        embeddings = self._embedder.encode([chunk.content for chunk in chunks])
        collection.add(
            ids=[chunk.doc_id for chunk in chunks],
            documents=[chunk.content for chunk in chunks],
            embeddings=embeddings,
            metadatas=[
                {"title": chunk.title, "source": chunk.source, **chunk.metadata} for chunk in chunks
            ],
        )
        logger.info("chroma_indexed", chunks=len(chunks))
        return len(chunks)

    def search(self, query: str, *, top_k: int = 4) -> list[RetrievedDocument]:
        collection = self._connect()
        if collection.count() == 0:
            return []

        embedding = self._embedder.encode([query], is_query=True)
        result = collection.query(
            query_embeddings=embedding,
            n_results=min(top_k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        ids = (result.get("ids") or [[]])[0]

        return [
            RetrievedDocument(
                doc_id=str(ids[position]),
                title=str((metadatas[position] or {}).get("title", "Knowledge base")),
                source=str((metadatas[position] or {}).get("source", "internal")),
                content=str(documents[position]),
                # Chroma returns cosine *distance*; convert so higher = closer.
                score=round(1.0 - float(distances[position]), 4),
            )
            for position in range(len(documents))
        ]

    def count(self) -> int:
        try:
            return int(self._connect().count())
        except Exception:
            return 0


class TfidfVectorStore(VectorStore):
    """In-memory TF-IDF cosine index over the knowledge base."""

    name = "tfidf-memory"

    def __init__(self) -> None:
        self._chunks: list[KnowledgeChunk] = []
        self._vectorizer: Any = None
        self._matrix: Any = None

    def index(self, chunks: list[KnowledgeChunk]) -> int:
        from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: PLC0415

        self._chunks = chunks
        if not chunks:
            self._vectorizer = None
            self._matrix = None
            return 0

        self._vectorizer = TfidfVectorizer(
            ngram_range=(1, 2), sublinear_tf=True, stop_words="english", min_df=1
        )
        self._matrix = self._vectorizer.fit_transform([chunk.content for chunk in chunks])
        logger.info("tfidf_store_indexed", chunks=len(chunks))
        return len(chunks)

    def search(self, query: str, *, top_k: int = 4) -> list[RetrievedDocument]:
        if self._vectorizer is None or self._matrix is None or not self._chunks:
            return []

        query_vector = self._vectorizer.transform([query])
        scores = (self._matrix @ query_vector.T).toarray().ravel()
        if not scores.any():
            return []

        order = np.argsort(scores)[::-1][:top_k]
        return [
            RetrievedDocument(
                doc_id=self._chunks[int(position)].doc_id,
                title=self._chunks[int(position)].title,
                source=self._chunks[int(position)].source,
                content=self._chunks[int(position)].content,
                score=round(float(scores[int(position)]), 4),
            )
            for position in order
            if scores[int(position)] > 0.01
        ]

    def count(self) -> int:
        return len(self._chunks)
