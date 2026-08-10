"""Agent 5 — report generation.

The LLM writes the prose; the system owns the numbers. The risk score, level
and category are computed before this agent runs and are copied into the report
verbatim, so a model that misreads the evidence can produce a badly worded
report but never a wrong verdict badge.
"""

from __future__ import annotations

import anyio

from app.agents import crew as crew_module
from app.agents.heuristics import report as report_rules
from app.agents.parsing import extract_json
from app.core.constants import RiskLevel, ScamCategory
from app.core.logging import get_logger
from app.schemas.classification import ClassificationResult
from app.schemas.factcheck import FactCheckResult
from app.schemas.report import RedFlag, RiskBreakdown, ScamReport
from app.schemas.social_engineering import SocialEngineeringResult
from app.schemas.transcript import Transcript

logger = get_logger(__name__)

_SEVERITY_ALIASES = {
    "critical": RiskLevel.CRITICAL,
    "severe": RiskLevel.CRITICAL,
    "high": RiskLevel.HIGH,
    "medium": RiskLevel.MEDIUM,
    "moderate": RiskLevel.MEDIUM,
    "low": RiskLevel.LOW,
    "minor": RiskLevel.LOW,
    "info": RiskLevel.LOW,
}


class ReportGeneratorAgent:
    """Writes the explainable assessment the user actually reads."""

    name = "report"

    def __init__(self, context: crew_module.CrewContext) -> None:
        self._context = context

    async def run(
        self,
        transcript: Transcript,
        classification: ClassificationResult,
        social: SocialEngineeringResult,
        fact_check: FactCheckResult,
        risk: RiskBreakdown,
        category: ScamCategory,
        *,
        use_llm: bool,
    ) -> ScamReport:
        deterministic = report_rules.build_report(
            transcript, classification, social, fact_check, risk, category
        )
        if not use_llm:
            return deterministic

        try:
            written = await self._run_llm(
                transcript, classification, social, fact_check, risk, category
            )
        except Exception as exc:
            logger.warning("report_llm_failed", error=str(exc), fallback="rules")
            return deterministic

        if written is None:
            logger.warning("report_llm_unusable", fallback="rules")
            return deterministic
        return written

    # ---- LLM path ---------------------------------------------------------
    async def _run_llm(
        self,
        transcript: Transcript,
        classification: ClassificationResult,
        social: SocialEngineeringResult,
        fact_check: FactCheckResult,
        risk: RiskBreakdown,
        category: ScamCategory,
    ) -> ScamReport | None:
        raw = await anyio.to_thread.run_sync(
            lambda: crew_module.run_report(
                self._context,
                transcript_text=transcript.timestamped_text(),
                classifier_summary=(
                    f"{classification.percentage}% scam probability from "
                    f"{classification.model_name}."
                ),
                fact_summary=self._describe_fact_check(fact_check),
                social_summary=self._describe_social(social),
                risk_score=risk.score,
                risk_level=risk.level.value,
            )
        )

        payload = extract_json(raw)
        if not isinstance(payload, dict):
            return None

        verdict = str(payload.get("verdict") or "").strip()
        summary = str(payload.get("summary") or "").strip()
        if not verdict or not summary:
            return None

        return ScamReport(
            verdict=verdict[:250],
            risk=risk,
            category=category,
            summary=summary,
            red_flags=self._parse_red_flags(payload.get("red_flags"), transcript),
            recommended_actions=[
                str(action).strip()
                for action in (payload.get("recommended_actions") or [])
                if str(action).strip()
            ][:6],
            caller_claims=[
                str(claim).strip()
                for claim in (payload.get("caller_claims") or [])
                if str(claim).strip()
            ][:8],
            is_fallback=False,
        )

    @staticmethod
    def _parse_red_flags(value: object, transcript: Transcript) -> list[RedFlag]:
        if not isinstance(value, list):
            return []

        flags: list[RedFlag] = []
        for item in value[:6]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                continue

            quote = str(item.get("quote") or "").strip()
            segment = transcript.locate(quote) if quote else None
            if quote and segment is None:
                quote = ""  # drop a quote the recording does not contain

            flags.append(
                RedFlag(
                    title=title[:150],
                    detail=str(item.get("detail") or "").strip(),
                    severity=_SEVERITY_ALIASES.get(
                        str(item.get("severity") or "").strip().lower(), RiskLevel.MEDIUM
                    ),
                    quote=segment.text.strip() if segment else None,
                    timestamp=segment.timestamp if segment else None,
                    source_agent="report",
                )
            )
        return flags

    @staticmethod
    def _describe_fact_check(fact_check: FactCheckResult) -> str:
        if not fact_check.verifications:
            return "No checkable claims were extracted."
        lines = [fact_check.summary] if fact_check.summary else []
        lines += [
            f"- [{verification.verdict.value}] {verification.claim.claim}"
            + (f" — {verification.explanation}" if verification.explanation else "")
            for verification in fact_check.verifications[:6]
        ]
        return "\n".join(lines)

    @staticmethod
    def _describe_social(social: SocialEngineeringResult) -> str:
        if not social.tactics:
            return "No manipulation tactics detected."
        lines = [social.summary] if social.summary else []
        lines += [
            f"- {detection.label} (severity {detection.severity:.2f})"
            + (f': "{detection.evidence[0].quote}"' if detection.evidence else "")
            for detection in social.tactics[:6]
        ]
        return "\n".join(lines)
