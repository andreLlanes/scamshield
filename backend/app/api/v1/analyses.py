"""Analysis endpoints — upload, poll, list, delete."""

from __future__ import annotations

import tempfile
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Query, UploadFile, status

from app.api.deps import AnalysisServiceDep, PipelineDep, SettingsDep
from app.core.constants import AnalysisStatus
from app.core.exceptions import PayloadTooLargeError, ScamShieldError
from app.core.logging import get_logger
from app.ml.transcription.stub import transcript_from_text
from app.schemas.analysis import (
    AnalysisAcceptedResponse,
    AnalysisCreateFromText,
    AnalysisDetail,
    AnalysisListResponse,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/analyses", tags=["analyses"])

_CHUNK = 1024 * 1024


@router.post(
    "",
    response_model=AnalysisAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a call recording for analysis",
)
async def create_analysis(
    background: BackgroundTasks,
    service: AnalysisServiceDep,
    pipeline: PipelineDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File(description="Audio recording of the suspicious call")],
) -> AnalysisAcceptedResponse:
    """Accept a recording, queue the pipeline, and return immediately.

    The upload is spooled to a temporary file while counting bytes so an
    oversized file is rejected before it reaches storage, and a large one never
    has to sit in memory.
    """
    try:
        with tempfile.SpooledTemporaryFile(max_size=8 * _CHUNK) as spool:
            size = 0
            while chunk := await file.read(_CHUNK):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise PayloadTooLargeError(
                        f"Upload exceeds the {settings.max_upload_mb} MB limit."
                    )
                spool.write(chunk)
            spool.seek(0)

            analysis = await service.create_from_upload(
                filename=file.filename or "recording",
                content_type=file.content_type,
                size_bytes=size,
                stream=spool,
            )
    finally:
        await file.close()

    if analysis.storage_key is None:
        # create_from_upload always sets it; this keeps the invariant explicit
        # rather than handing None to a worker that would fail deep in the pipeline.
        raise ScamShieldError("The recording was not stored; cannot start the analysis.")

    background.add_task(pipeline.run_from_audio, analysis.id, analysis.storage_key)

    return AnalysisAcceptedResponse(
        id=analysis.id,
        status=AnalysisStatus(analysis.status),
        filename=analysis.filename,
        poll_url=f"{settings.api_prefix}/analyses/{analysis.id}",
    )


@router.post(
    "/text",
    response_model=AnalysisAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Analyse a transcript directly (skips speech-to-text)",
)
async def create_analysis_from_text(
    payload: AnalysisCreateFromText,
    background: BackgroundTasks,
    service: AnalysisServiceDep,
    pipeline: PipelineDep,
    settings: SettingsDep,
) -> AnalysisAcceptedResponse:
    """Run Agents 2-5 over a transcript supplied as text.

    Useful for testing, for demos on machines without a Whisper install, and for
    users who already have a transcript.
    """
    analysis = await service.create_from_text(
        filename=payload.filename, size_bytes=len(payload.transcript.encode("utf-8"))
    )
    transcript = transcript_from_text(
        payload.transcript, language=payload.language, model="user-supplied", backend="text-input"
    )
    background.add_task(pipeline.run_from_transcript, analysis.id, transcript)

    return AnalysisAcceptedResponse(
        id=analysis.id,
        status=AnalysisStatus(analysis.status),
        filename=analysis.filename,
        poll_url=f"{settings.api_prefix}/analyses/{analysis.id}",
    )


@router.get("", response_model=AnalysisListResponse, summary="List analyses")
async def list_analyses(
    service: AnalysisServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_filter: Annotated[AnalysisStatus | None, Query(alias="status")] = None,
) -> AnalysisListResponse:
    items, total = await service.list(limit=limit, offset=offset, status=status_filter)
    return AnalysisListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{analysis_id}", response_model=AnalysisDetail, summary="Get one analysis")
async def get_analysis(analysis_id: str, service: AnalysisServiceDep) -> AnalysisDetail:
    return await service.get_detail(analysis_id)


@router.delete(
    "/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an analysis"
)
async def delete_analysis(analysis_id: str, service: AnalysisServiceDep) -> None:
    await service.delete(analysis_id)
