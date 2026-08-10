"""Health and readiness endpoints.

``/health/components`` reports each subsystem separately and, when one has
degraded to a fallback, says what it degraded *to*. The frontend renders this
as a status strip so a demo never silently misrepresents which models ran.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.agents.llm import llm_status
from app.api.deps import ClassifierDep, RetrieverDep, SettingsDep, TranscriberDep
from app.schemas.analysis import ComponentHealth, HealthResponse

router = APIRouter(tags=["health"])

VERSION = "0.1.0"


@router.get("/health", summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": VERSION}


@router.get("/health/components", response_model=HealthResponse, summary="Component readiness")
async def components(
    settings: SettingsDep,
    transcriber: TranscriberDep,
    classifier: ClassifierDep,
    retriever: RetrieverDep,
) -> HealthResponse:
    transcription = transcriber.describe()
    asr_ready = transcriber.is_ready()

    classifier_info = classifier.describe()
    classifier_ready = bool(classifier_info.get("trained"))

    await retriever.ensure_indexed()
    rag_info = retriever.describe()
    rag_ready = bool(rag_info.get("chunks"))

    llm_ready, llm_detail = llm_status(settings)

    return HealthResponse(
        status="ok",
        version=VERSION,
        environment=settings.environment,
        components={
            "transcription": ComponentHealth(
                ready=asr_ready,
                detail=(
                    f"{transcription['backend']} · {transcription['model']}"
                    if asr_ready
                    else "No Whisper runtime installed — audio upload is unavailable"
                ),
                degraded_to=None if asr_ready else "transcript-only mode",
            ),
            "classifier": ComponentHealth(
                ready=classifier_ready,
                detail=str(classifier_info.get("model")),
                degraded_to=None if classifier_ready else "weighted scam lexicon",
            ),
            "knowledge_base": ComponentHealth(
                ready=rag_ready,
                detail=(
                    f"{rag_info['store']} · {rag_info['chunks']} chunks · "
                    f"{rag_info['embedding_model']}"
                ),
                degraded_to=None if rag_info["store"] == "chromadb" else "in-memory TF-IDF index",
            ),
            "agents": ComponentHealth(
                ready=llm_ready,
                detail=llm_detail,
                degraded_to=None if llm_ready else "deterministic rule-based analyzers",
            ),
        },
    )
