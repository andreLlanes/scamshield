"""Pydantic contracts shared by the agents, the API and the database layer."""

from app.schemas.analysis import (
    AnalysisAcceptedResponse,
    AnalysisCreateFromText,
    AnalysisDetail,
    AnalysisListResponse,
    AnalysisSummary,
    ComponentHealth,
    HealthResponse,
)
from app.schemas.classification import ClassificationResult, FeatureContribution
from app.schemas.factcheck import (
    ClaimVerification,
    FactCheckResult,
    FactualClaim,
    RetrievedDocument,
)
from app.schemas.report import (
    AgentTrace,
    AnalysisEvidence,
    EvidenceWeight,
    RedFlag,
    RiskBreakdown,
    ScamReport,
)
from app.schemas.social_engineering import (
    SocialEngineeringResult,
    TacticDetection,
    TacticEvidence,
)
from app.schemas.transcript import Transcript, TranscriptSegment

__all__ = [
    "AgentTrace",
    "AnalysisAcceptedResponse",
    "AnalysisCreateFromText",
    "AnalysisDetail",
    "AnalysisEvidence",
    "AnalysisListResponse",
    "AnalysisSummary",
    "ClaimVerification",
    "ClassificationResult",
    "ComponentHealth",
    "EvidenceWeight",
    "FactCheckResult",
    "FactualClaim",
    "FeatureContribution",
    "HealthResponse",
    "RedFlag",
    "RetrievedDocument",
    "RiskBreakdown",
    "ScamReport",
    "SocialEngineeringResult",
    "TacticDetection",
    "TacticEvidence",
    "Transcript",
    "TranscriptSegment",
]
