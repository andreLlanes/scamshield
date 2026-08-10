"""Agent 3 — fact verification.

Runs the CrewAI fact-check agent when an LLM is configured, and the rule-based
verifier otherwise. LLM output is grounded before it is accepted: a quote that
does not appear in the transcript is discarded, and a claim retained without a
quote is downgraded to ``unverified`` so a hallucinated contradiction can never
drive the risk score.
"""

from __future__ import annotations

import anyio

from app.agents import crew as crew_module
from app.agents.heuristics import claims as claim_rules
from app.agents.parsing import coerce_float, extract_json
from app.core.constants import ClaimVerdict
from app.core.logging import get_logger
from app.ml.rag.retriever import KnowledgeRetriever
from app.schemas.factcheck import ClaimVerification, FactCheckResult, FactualClaim
from app.schemas.transcript import Transcript

logger = get_logger(__name__)

_MAX_CLAIMS = 8


class FactCheckAgent:
    """Extracts and verifies the caller's factual claims."""

    name = "fact_check"

    def __init__(self, context: crew_module.CrewContext) -> None:
        self._context = context

    @property
    def _retriever(self) -> KnowledgeRetriever:
        return self._context.retriever

    async def run(self, transcript: Transcript, *, use_llm: bool) -> FactCheckResult:
        if use_llm:
            try:
                result = await self._run_llm(transcript)
                if result is not None:
                    return result
                logger.warning("fact_check_llm_unusable", fallback="rules")
            except Exception as exc:
                logger.warning("fact_check_llm_failed", error=str(exc), fallback="rules")

        return await claim_rules.extract_and_verify(transcript, self._retriever)

    # ---- LLM path ---------------------------------------------------------
    async def _run_llm(self, transcript: Transcript) -> FactCheckResult | None:
        await self._retriever.ensure_indexed()
        raw = await anyio.to_thread.run_sync(
            lambda: crew_module.run_fact_check(self._context, transcript.timestamped_text())
        )

        payload = extract_json(raw)
        if not isinstance(payload, dict):
            return None
        items = payload.get("claims")
        if not isinstance(items, list) or not items:
            return None

        verifications = self._parse_claims(items, transcript)
        if not verifications:
            return None

        summary = str(payload.get("summary") or "").strip()
        result = FactCheckResult(verifications=verifications, summary=summary, is_fallback=False)
        if not result.summary:
            result.summary = (
                f"{result.contradicted_count} of {len(verifications)} checkable claims "
                "contradict documented policy."
            )
        return result

    def _parse_claims(self, items: list[object], transcript: Transcript) -> list[ClaimVerification]:
        verifications: list[ClaimVerification] = []
        for item in items[:_MAX_CLAIMS]:
            if not isinstance(item, dict):
                continue
            claim_text = str(item.get("claim") or "").strip()
            if not claim_text:
                continue

            quote = str(item.get("quote") or "").strip()
            segment = transcript.locate(quote) if quote else None
            if quote and segment is None:
                # The model quoted something that is not in the recording.
                logger.debug("ungrounded_quote_dropped", quote=quote[:80])
                quote = ""

            verdict = self._parse_verdict(item.get("verdict"))
            if verdict == ClaimVerdict.CONTRADICTED and not quote:
                # Refuse to let an unquoted contradiction escalate the score.
                verdict = ClaimVerdict.UNVERIFIED

            verifications.append(
                ClaimVerification(
                    claim=FactualClaim(
                        claim=claim_text,
                        quote=quote,
                        timestamp=segment.timestamp if segment else None,
                        category=str(item.get("category") or "general").strip().lower(),
                    ),
                    verdict=verdict,
                    confidence=coerce_float(item.get("confidence"), 0.6),
                    explanation=str(item.get("explanation") or "").strip(),
                )
            )
        return verifications

    @staticmethod
    def _parse_verdict(value: object) -> ClaimVerdict:
        text = str(value or "").strip().lower()
        if text.startswith("contradict") or text in {"false", "refuted", "disproven"}:
            return ClaimVerdict.CONTRADICTED
        if text.startswith("verif") or text in {"true", "supported", "confirmed"}:
            return ClaimVerdict.VERIFIED
        return ClaimVerdict.UNVERIFIED

    async def attach_evidence(self, result: FactCheckResult) -> FactCheckResult:
        """Attach the retrieved passages behind each verdict, for the UI."""
        missing = [
            verification
            for verification in result.verifications
            if not verification.evidence and verification.claim.claim
        ]
        if not missing:
            return result

        evidence_map = await self._retriever.search_many(
            [verification.claim.claim for verification in missing], top_k=2
        )
        for verification in missing:
            verification.evidence = evidence_map.get(verification.claim.claim, [])
        return result
