"""Knowledge-base and reference endpoints.

Exposing retrieval directly is what makes Agent 3 auditable: a reviewer can ask
the same question the agent asked and see the passages it was given.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.deps import RetrieverDep
from app.core.constants import TACTIC_DESCRIPTIONS, TACTIC_LABELS, TacticType
from app.schemas.factcheck import RetrievedDocument

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class KnowledgeSearchResponse(BaseModel):
    query: str
    store: str
    results: list[RetrievedDocument]


class KnowledgeStatsResponse(BaseModel):
    store: str
    embedding_model: str
    chunks: int


class TacticReference(BaseModel):
    id: str
    label: str
    description: str


@router.get("/search", response_model=KnowledgeSearchResponse, summary="Search the knowledge base")
async def search(
    retriever: RetrieverDep,
    q: Annotated[str, Query(min_length=3, max_length=500, description="Question to retrieve for")],
    top_k: Annotated[int, Query(ge=1, le=10)] = 4,
) -> KnowledgeSearchResponse:
    results = await retriever.search(q, top_k=top_k)
    return KnowledgeSearchResponse(query=q, store=retriever.store.name, results=results)


@router.get("/stats", response_model=KnowledgeStatsResponse, summary="Vector store status")
async def stats(retriever: RetrieverDep) -> KnowledgeStatsResponse:
    await retriever.ensure_indexed()
    info = retriever.describe()
    return KnowledgeStatsResponse(
        store=info["store"],
        embedding_model=info["embedding_model"],
        chunks=info["chunks"],
    )


@router.post("/reindex", response_model=KnowledgeStatsResponse, summary="Rebuild the index")
async def reindex(retriever: RetrieverDep) -> KnowledgeStatsResponse:
    """Re-read the markdown knowledge base and rebuild the collection."""
    await retriever.ensure_indexed(force=True)
    info = retriever.describe()
    return KnowledgeStatsResponse(
        store=info["store"],
        embedding_model=info["embedding_model"],
        chunks=info["chunks"],
    )


@router.get("/tactics", response_model=list[TacticReference], summary="Tactic reference list")
async def tactics() -> list[TacticReference]:
    """The tactic vocabulary, for the frontend legend and glossary."""
    return [
        TacticReference(
            id=tactic.value,
            label=TACTIC_LABELS[tactic],
            description=TACTIC_DESCRIPTIONS[tactic],
        )
        for tactic in TacticType
    ]
