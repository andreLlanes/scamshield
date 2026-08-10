"""Agent 2 output — the classical ML scam probability."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FeatureContribution(BaseModel):
    """One n-gram and how much it pushed the prediction."""

    feature: str = Field(..., description="TF-IDF term the model reacted to.")
    weight: float = Field(..., description="Signed contribution; positive means 'more scam-like'.")
    occurrences: int = Field(default=1, ge=1)


class ClassificationResult(BaseModel):
    """Quantitative scam probability plus the terms that drove it."""

    scam_probability: float = Field(..., ge=0.0, le=1.0)
    label: str = Field(..., description="``scam`` or ``legitimate``.")
    model_name: str = Field(default="tfidf+xgboost")
    is_fallback: bool = Field(
        default=False,
        description="True when the trained artifact was unavailable and the lexicon scorer ran.",
    )
    top_features: list[FeatureContribution] = Field(default_factory=list)

    model_config = {"protected_namespaces": ()}

    @property
    def percentage(self) -> float:
        return round(self.scam_probability * 100, 1)
