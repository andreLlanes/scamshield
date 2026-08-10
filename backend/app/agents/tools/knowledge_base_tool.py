"""CrewAI tool exposing the RAG knowledge base to the fact-check agent.

This is the retrieval half of Agent 3: the agent decides *what* to look up, the
tool performs the vector search. Built lazily so importing this module never
requires crewai to be installed.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.ml.rag.retriever import KnowledgeRetriever

logger = get_logger(__name__)

_NO_RESULTS = (
    "No relevant passage found in the knowledge base. Treat the claim as 'unverified' "
    "rather than guessing."
)


def search_knowledge_base(retriever: KnowledgeRetriever, question: str, top_k: int = 3) -> str:
    """Run a synchronous KB search and format it for an LLM to read."""
    retriever.ensure_indexed_sync()
    documents = retriever.store.search(question, top_k=top_k)
    if not documents:
        return _NO_RESULTS

    blocks = [
        f"[{index}] {document.title} (source: {document.source}, similarity {document.score:.2f})\n"
        f"{document.content.strip()}"
        for index, document in enumerate(documents, start=1)
    ]
    return "\n\n".join(blocks)


def build_knowledge_base_tool(retriever: KnowledgeRetriever) -> Any:
    """Construct the CrewAI tool bound to ``retriever``."""
    from crewai.tools import BaseTool  # noqa: PLC0415  — optional extra
    from pydantic import BaseModel, Field  # noqa: PLC0415

    class _Input(BaseModel):
        question: str = Field(
            ...,
            description=(
                "A short question about one claim, e.g. 'Do banks ask customers for their OTP?'"
            ),
        )

    class KnowledgeBaseSearchTool(BaseTool):
        name: str = "Knowledge Base Search"
        description: str = (
            "Search ScamShield's verified knowledge base of bank policies, government "
            "agency procedures, payment red flags and scam patterns. Use it once per "
            "claim before deciding a verdict. Input: a single short question."
        )
        args_schema: type[BaseModel] = _Input

        def _run(self, question: str) -> str:
            try:
                return search_knowledge_base(retriever, question)
            except Exception as exc:  # a tool crash must not kill the crew
                logger.error("kb_tool_failed", error=str(exc), question=question)
                return _NO_RESULTS

    return KnowledgeBaseSearchTool()
