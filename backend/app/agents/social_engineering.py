"""Agent 4 — social engineering analysis.

The LLM path adds nuance the regexes miss (implied threats, tone), but its
findings are merged with the rule-based pass rather than replacing it: the
rules never miss an explicit "do not hang up", and the LLM never invents a
tactic that has no quote in the recording.
"""

from __future__ import annotations

import anyio

from app.agents import crew as crew_module
from app.agents.heuristics import tactics as tactic_rules
from app.agents.parsing import coerce_float, extract_json
from app.core.constants import TacticType
from app.core.logging import get_logger
from app.schemas.social_engineering import (
    SocialEngineeringResult,
    TacticDetection,
    TacticEvidence,
)
from app.schemas.transcript import Transcript

logger = get_logger(__name__)


class SocialEngineeringAgent:
    """Detects psychological manipulation tactics used by the caller."""

    name = "social_engineering"

    def __init__(self, context: crew_module.CrewContext) -> None:
        self._context = context

    async def run(self, transcript: Transcript, *, use_llm: bool) -> SocialEngineeringResult:
        baseline = tactic_rules.analyze(transcript)
        if not use_llm:
            return baseline

        try:
            llm_result = await self._run_llm(transcript)
        except Exception as exc:
            logger.warning("social_engineering_llm_failed", error=str(exc), fallback="rules")
            return baseline

        if llm_result is None:
            logger.warning("social_engineering_llm_unusable", fallback="rules")
            return baseline

        return self._merge(baseline, llm_result)

    # ---- LLM path ---------------------------------------------------------
    async def _run_llm(self, transcript: Transcript) -> SocialEngineeringResult | None:
        raw = await anyio.to_thread.run_sync(
            lambda: crew_module.run_social_engineering(self._context, transcript.timestamped_text())
        )
        payload = extract_json(raw)
        if not isinstance(payload, dict):
            return None
        items = payload.get("tactics")
        if not isinstance(items, list):
            return None

        detections: list[TacticDetection] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            tactic = self._parse_tactic(item.get("tactic"))
            if tactic is None:
                continue

            evidence = self._parse_evidence(item.get("evidence"), transcript)
            if not evidence:
                # A tactic with no line from the recording behind it is not a finding.
                continue

            detections.append(
                TacticDetection(
                    tactic=tactic,
                    confidence=coerce_float(item.get("confidence"), 0.7),
                    severity=coerce_float(item.get("severity"), 0.6),
                    evidence=evidence[:3],
                )
            )

        return SocialEngineeringResult(
            tactics=detections,
            summary=str(payload.get("summary") or "").strip(),
            manipulation_score=SocialEngineeringResult.score_from(detections),
            is_fallback=False,
        )

    @staticmethod
    def _parse_tactic(value: object) -> TacticType | None:
        text = str(value or "").strip().lower().replace(" ", "_")
        try:
            return TacticType(text)
        except ValueError:
            aliases = {
                "false_trust": TacticType.TRUST,
                "social_proof": TacticType.TRUST,
                "intimidation": TacticType.FEAR,
                "threat": TacticType.FEAR,
                "time_pressure": TacticType.URGENCY,
                "secrecy": TacticType.ISOLATION,
                "greed": TacticType.REWARD,
                "limited_time": TacticType.SCARCITY,
            }
            return aliases.get(text)

    @staticmethod
    def _parse_evidence(value: object, transcript: Transcript) -> list[TacticEvidence]:
        if not isinstance(value, list):
            return []

        evidence: list[TacticEvidence] = []
        for item in value:
            quote = (
                str(item.get("quote") or "").strip()
                if isinstance(item, dict)
                else str(item).strip()
            )
            if not quote:
                continue
            segment = transcript.locate(quote)
            if segment is None:
                logger.debug("ungrounded_tactic_quote_dropped", quote=quote[:80])
                continue
            explanation = (
                str(item.get("explanation") or "").strip() if isinstance(item, dict) else ""
            )
            evidence.append(
                TacticEvidence(
                    quote=segment.text.strip(),
                    timestamp=segment.timestamp,
                    explanation=explanation,
                )
            )
        return evidence

    @staticmethod
    def _merge(
        baseline: SocialEngineeringResult, llm: SocialEngineeringResult
    ) -> SocialEngineeringResult:
        """Union of both passes; the higher-confidence detection wins per tactic."""
        merged: dict[TacticType, TacticDetection] = {
            detection.tactic: detection for detection in baseline.tactics
        }
        for detection in llm.tactics:
            existing = merged.get(detection.tactic)
            if existing is None:
                merged[detection.tactic] = detection
                continue
            merged[detection.tactic] = TacticDetection(
                tactic=detection.tactic,
                confidence=max(existing.confidence, detection.confidence),
                severity=max(existing.severity, detection.severity),
                evidence=(existing.evidence + detection.evidence)[:3],
            )

        detections = sorted(merged.values(), key=lambda d: d.confidence * d.severity, reverse=True)
        summary = llm.summary or baseline.summary
        return SocialEngineeringResult(
            tactics=detections,
            summary=summary,
            manipulation_score=SocialEngineeringResult.score_from(detections),
            is_fallback=False,
        )
