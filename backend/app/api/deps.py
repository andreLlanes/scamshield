"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.ml.classifier.service import ScamClassifierService, get_classifier_service
from app.ml.rag.retriever import KnowledgeRetriever, get_retriever
from app.ml.transcription.service import TranscriptionService, get_transcription_service
from app.services.analysis_service import AnalysisService
from app.services.pipeline import AnalysisPipeline, get_pipeline

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
PipelineDep = Annotated[AnalysisPipeline, Depends(get_pipeline)]
ClassifierDep = Annotated[ScamClassifierService, Depends(get_classifier_service)]
RetrieverDep = Annotated[KnowledgeRetriever, Depends(get_retriever)]
TranscriberDep = Annotated[TranscriptionService, Depends(get_transcription_service)]


def get_analysis_service(session: SessionDep, settings: SettingsDep) -> AnalysisService:
    return AnalysisService(session, settings=settings)


AnalysisServiceDep = Annotated[AnalysisService, Depends(get_analysis_service)]
