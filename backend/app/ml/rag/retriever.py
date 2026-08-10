"""Agent 3's retrieval facade.

Owns store selection, first-use indexing, and the query surface the fact-check
agent calls.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TypedDict

import anyio

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.ml.rag.documents import KnowledgeChunk, load_knowledge_base
from app.ml.rag.vector_store import ChromaVectorStore, TfidfVectorStore, VectorStore
from app.schemas.factcheck import RetrievedDocument

logger = get_logger(__name__)


class RetrieverInfo(TypedDict):
    """Shape of :meth:`KnowledgeRetriever.describe`, for the health endpoint."""

    store: str
    embedding_model: str
    chunks: int


class KnowledgeRetriever:
    """Loads the knowledge base into a vector store and answers queries."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._store: VectorStore | None = None
        self._ready = False
        self._lock = anyio.Lock()

    def _build_store(self) -> VectorStore:
        if ChromaVectorStore.is_available():
            return ChromaVectorStore(self._settings)
        logger.warning(
            "vector_store_degraded",
            reason="chromadb/sentence-transformers not installed",
            fallback=TfidfVectorStore.name,
            hint="pip install -e '.[rag]'",
        )
        return TfidfVectorStore()

    @property
    def store(self) -> VectorStore:
        if self._store is None:
            self._store = self._build_store()
        return self._store

    def load_chunks(self) -> list[KnowledgeChunk]:
        return load_knowledge_base(self._settings.resolve(self._settings.knowledge_base_path))

    def ensure_indexed_sync(self, *, force: bool = False) -> int:
        """Index the knowledge base if the store is empty (or ``force``)."""
        store = self.store
        if not force and store.count() > 0:
            self._ready = True
            return store.count()

        chunks = self.load_chunks()
        count = store.index(chunks)
        self._ready = count > 0
        return count

    async def ensure_indexed(self, *, force: bool = False) -> int:
        async with self._lock:
            return await anyio.to_thread.run_sync(lambda: self.ensure_indexed_sync(force=force))

    def is_ready(self) -> bool:
        return self._ready or self.store.count() > 0

    def describe(self) -> RetrieverInfo:
        return RetrieverInfo(
            store=self.store.name,
            embedding_model=(
                self._settings.embedding_model
                if self.store.name == "chromadb"
                else "tfidf (no embeddings)"
            ),
            chunks=self.store.count(),
        )

    async def search(self, query: str, *, top_k: int | None = None) -> list[RetrievedDocument]:
        """Retrieve knowledge-base evidence relevant to ``query``."""
        await self.ensure_indexed()
        k = top_k or self._settings.rag_top_k
        store = self.store
        return await anyio.to_thread.run_sync(lambda: store.search(query, top_k=k))

    async def search_many(
        self, queries: list[str], *, top_k: int | None = None
    ) -> dict[str, list[RetrievedDocument]]:
        """Retrieve for several claims concurrently."""
        await self.ensure_indexed()
        results: dict[str, list[RetrievedDocument]] = {}

        async def _run(query: str) -> None:
            results[query] = await self.search(query, top_k=top_k)

        async with anyio.create_task_group() as group:
            for query in queries:
                group.start_soon(_run, query)
        return results


@lru_cache(maxsize=1)
def get_retriever() -> KnowledgeRetriever:
    return KnowledgeRetriever()
