"""The orchestrator agent.

Owns the analysis half of the workflow: it decides which specialists run, runs
the independent ones concurrently, computes the risk score from their outputs,
and hands everything to the report writer. Transcription and persistence sit
outside it, in ``app.services.pipeline``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import anyio

from app.agents import crew as crew_module
from app.agents.fact_checker import FactCheckAgent
from app.agents.report_generator import ReportGeneratorAgent
from app.agents.social_engineering import SocialEngineeringAgent
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.ml.classifier.service import ScamClassifierService, get_classifier_service
from app.ml.rag.retriever import KnowledgeRetriever, get_retriever
from app.schemas.classification import ClassificationResult
from app.schemas.factcheck import FactCheckResult
from app.schemas.report import AgentTrace, AnalysisEvidence, ScamReport
from app.schemas.social_engineering import SocialEngineeringResult
from app.schemas.transcript import Transcript
from app.services import scoring

logger = get_logger(__name__)


@dataclass
class OrchestrationResult:
    """Everything the analysis half of the pipeline produced."""

    evidence: AnalysisEvidence
    report: ScamReport
    traces: list[AgentTrace] = field(default_factory=list)
    used_llm: bool = False


class _Timer:
    """Records per-agent wall time so the UI can show an agent timeline."""

    def __init__(self) -> None:
        self._origin = time.perf_counter()
        self.traces: list[AgentTrace] = []

    def record(
        self, agent: str, started: float, *, status: str = "completed", detail: str = ""
    ) -> None:
        self.traces.append(
            AgentTrace(
                agent=agent,
                status=status,
                started_at=round(started - self._origin, 3),
                duration_seconds=round(time.perf_counter() - started, 3),
                detail=detail,
            )
        )

    def now(self) -> float:
        return time.perf_counter()


class Orchestrator:
    """Coordinates Agents 2-5 over a transcript."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        classifier: ScamClassifierService | None = None,
        retriever: KnowledgeRetriever | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._classifier = classifier or get_classifier_service()
        self._retriever = retriever or get_retriever()
        self._context = crew_module.CrewContext(
            retriever=self._retriever, classifier=self._classifier
        )
        self._fact_checker = FactCheckAgent(self._context)
        self._social = SocialEngineeringAgent(self._context)
        self._reporter = ReportGeneratorAgent(self._context)

    async def analyze(self, transcript: Transcript) -> OrchestrationResult:
        """Run the full analysis and return evidence, report and traces."""
        timer = _Timer()
        use_llm = self._settings.agents_enabled and crew_module.is_crew_available()
        logger.info("orchestration_started", use_llm=use_llm, words=transcript.word_count)

        classification: ClassificationResult | None = None
        fact_check: FactCheckResult | None = None
        social: SocialEngineeringResult | None = None

        # Agents 2, 3 and 4 are independent — run them concurrently.
        async def _classify() -> None:
            nonlocal classification
            started = timer.now()
            classification = await self._classifier.predict(transcript.text)
            timer.record(
                "classifier",
                started,
                detail=f"{classification.percentage}% scam ({classification.model_name})",
            )

        async def _verify() -> None:
            nonlocal fact_check
            started = timer.now()
            fact_check = await self._fact_checker.run(transcript, use_llm=use_llm)
            fact_check = await self._fact_checker.attach_evidence(fact_check)
            timer.record(
                "fact_check",
                started,
                detail=(
                    f"{len(fact_check.verifications)} claims, "
                    f"{fact_check.contradicted_count} contradicted"
                    + (" (rules)" if fact_check.is_fallback else " (LLM)")
                ),
            )

        async def _social_engineering() -> None:
            nonlocal social
            started = timer.now()
            social = await self._social.run(transcript, use_llm=use_llm)
            timer.record(
                "social_engineering",
                started,
                detail=(
                    f"{len(social.tactics)} tactics"
                    + (" (rules)" if social.is_fallback else " (LLM+rules)")
                ),
            )

        async with anyio.create_task_group() as group:
            group.start_soon(_classify)
            group.start_soon(_verify)
            group.start_soon(_social_engineering)

        assert classification is not None and fact_check is not None and social is not None

        risk = scoring.compute_risk(classification, social, fact_check, settings=self._settings)
        category = scoring.infer_category(transcript.text, risk)

        started = timer.now()
        report = await self._reporter.run(
            transcript, classification, social, fact_check, risk, category, use_llm=use_llm
        )
        timer.record(
            "report",
            started,
            detail=f"{risk.score}/100 {risk.level.value}"
            + (" (rules)" if report.is_fallback else " (LLM)"),
        )

        logger.info(
            "orchestration_completed",
            risk_score=risk.score,
            risk_level=risk.level.value,
            category=category.value,
        )

        return OrchestrationResult(
            evidence=AnalysisEvidence(
                classification=classification,
                fact_check=fact_check,
                social_engineering=social,
            ),
            report=report,
            traces=timer.traces,
            used_llm=use_llm,
        )
