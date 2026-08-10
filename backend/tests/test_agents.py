"""Unit tests for the deterministic analyzers and the scoring maths."""

from __future__ import annotations

import pytest

from app.agents.heuristics import claims as claim_rules
from app.agents.heuristics import tactics as tactic_rules
from app.agents.parsing import coerce_float, extract_json
from app.core.constants import ClaimVerdict, RiskLevel, TacticType, risk_level_for
from app.ml.classifier import lexicon
from app.ml.rag.retriever import KnowledgeRetriever
from app.ml.transcription.stub import transcript_from_text
from app.schemas.classification import ClassificationResult
from app.schemas.factcheck import FactCheckResult
from app.schemas.social_engineering import SocialEngineeringResult, TacticDetection
from app.services import scoring


class TestTacticDetection:
    def test_detects_the_core_tactics_of_a_scam_call(self, scam_transcript: str) -> None:
        result = tactic_rules.analyze(transcript_from_text(scam_transcript))
        detected = set(result.detected_tactics)

        assert TacticType.AUTHORITY in detected
        assert TacticType.URGENCY in detected
        assert TacticType.PRESSURE in detected
        assert TacticType.ISOLATION in detected
        assert result.manipulation_score > 0.8

    def test_legitimate_call_scores_low(self, legit_transcript: str) -> None:
        result = tactic_rules.analyze(transcript_from_text(legit_transcript))
        assert result.manipulation_score < 0.5

    def test_every_detection_carries_a_quote(self, scam_transcript: str) -> None:
        result = tactic_rules.analyze(transcript_from_text(scam_transcript))
        for detection in result.tactics:
            assert detection.evidence, f"{detection.tactic} has no evidence"
            assert detection.evidence[0].quote.strip()

    def test_score_saturates_rather_than_averaging(self) -> None:
        one_strong = [TacticDetection(tactic=TacticType.ISOLATION, confidence=0.9, severity=1.0)]
        several_weak = [
            TacticDetection(tactic=tactic, confidence=0.5, severity=0.5)
            for tactic in (TacticType.TRUST, TacticType.SCARCITY, TacticType.REWARD)
        ]
        assert SocialEngineeringResult.score_from(one_strong) > 0.85
        assert 0.4 < SocialEngineeringResult.score_from(several_weak) < 0.7
        assert SocialEngineeringResult.score_from([]) == 0.0


class TestClaimVerification:
    async def test_contradicts_otp_request(self, scam_transcript: str) -> None:
        retriever = KnowledgeRetriever()
        result = await claim_rules.extract_and_verify(
            transcript_from_text(scam_transcript), retriever
        )

        assert result.contradicted_count >= 1
        contradicted = [
            item for item in result.verifications if item.verdict == ClaimVerdict.CONTRADICTED
        ]
        assert any("code" in item.claim.claim.lower() for item in contradicted)
        assert contradicted[0].evidence, "a contradiction must cite knowledge-base evidence"

    async def test_legitimate_call_has_no_contradictions(self, legit_transcript: str) -> None:
        retriever = KnowledgeRetriever()
        result = await claim_rules.extract_and_verify(
            transcript_from_text(legit_transcript), retriever
        )
        assert result.contradicted_count == 0
        assert any(item.verdict == ClaimVerdict.VERIFIED for item in result.verifications)

    async def test_identity_claims_are_unverified_not_verified(self, legit_transcript: str) -> None:
        retriever = KnowledgeRetriever()
        result = await claim_rules.extract_and_verify(
            transcript_from_text(legit_transcript), retriever
        )
        identity = [item for item in result.verifications if item.claim.category == "identity"]
        assert all(item.verdict != ClaimVerdict.VERIFIED for item in identity)


class TestLexicon:
    def test_scam_text_scores_above_legitimate_text(
        self, scam_transcript: str, legit_transcript: str
    ) -> None:
        scam_score, scam_hits = lexicon.score(scam_transcript)
        legit_score, _ = lexicon.score(legit_transcript)

        assert scam_score > 0.7
        assert legit_score < 0.3
        assert scam_hits


class TestScoring:
    @staticmethod
    def _evidence(prob: float, manipulation: float, contradicted: int) -> tuple:
        classification = ClassificationResult(scam_probability=prob, label="scam")
        social = SocialEngineeringResult(manipulation_score=manipulation)
        fact_check = FactCheckResult(verifications=[])
        if contradicted:
            from app.schemas.factcheck import ClaimVerification, FactualClaim

            fact_check.verifications = [
                ClaimVerification(claim=FactualClaim(claim="x"), verdict=ClaimVerdict.CONTRADICTED)
                for _ in range(contradicted)
            ]
        return classification, social, fact_check

    def test_weights_are_normalised_and_components_explain_the_score(self) -> None:
        risk = scoring.compute_risk(*self._evidence(0.9, 0.8, 0))
        weighted = [c for c in risk.components if c.source != "override"]

        assert pytest.approx(sum(c.weight for c in weighted), abs=1e-6) == 1.0
        assert pytest.approx(sum(c.weighted_points for c in weighted), abs=0.1) == risk.score
        assert all(component.rationale for component in risk.components)

    def test_a_contradicted_claim_floors_the_score(self) -> None:
        risk = scoring.compute_risk(*self._evidence(0.05, 0.05, 1))
        assert risk.score >= 78.0
        assert risk.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        assert any(component.source == "override" for component in risk.components)

    def test_clean_call_scores_safe(self) -> None:
        risk = scoring.compute_risk(*self._evidence(0.02, 0.0, 0))
        assert risk.level == RiskLevel.SAFE

    @pytest.mark.parametrize(
        ("score", "level"),
        [
            (0.0, RiskLevel.SAFE),
            (19.9, RiskLevel.SAFE),
            (20.0, RiskLevel.LOW),
            (40.0, RiskLevel.MEDIUM),
            (65.0, RiskLevel.HIGH),
            (85.0, RiskLevel.CRITICAL),
            (100.0, RiskLevel.CRITICAL),
        ],
    )
    def test_risk_bands(self, score: float, level: RiskLevel) -> None:
        assert risk_level_for(score) == level


class TestParsing:
    @pytest.mark.parametrize(
        "raw",
        [
            '{"a": 1}',
            'Here is the result:\n```json\n{"a": 1}\n```',
            'Sure!\n{"a": 1}\nHope that helps.',
            '{"a": 1,}',
        ],
    )
    def test_recovers_json_from_messy_output(self, raw: str) -> None:
        assert extract_json(raw) == {"a": 1}

    def test_ignores_braces_inside_strings(self) -> None:
        assert extract_json('{"quote": "he said {not json}"}') == {"quote": "he said {not json}"}

    def test_returns_none_when_nothing_parseable(self) -> None:
        assert extract_json("I could not complete the task.") is None

    @pytest.mark.parametrize(
        ("value", "expected"),
        [(0.8, 0.8), ("0.8", 0.8), ("80%", 0.8), (80, 0.8), ("nonsense", 0.5), (None, 0.5)],
    )
    def test_coerce_float_handles_model_formats(self, value: object, expected: float) -> None:
        assert coerce_float(value) == pytest.approx(expected)
