"""Agent 2 — classical ML scam classification (TF-IDF + XGBoost)."""

from app.ml.classifier.service import ScamClassifierService, get_classifier_service

__all__ = ["ScamClassifierService", "get_classifier_service"]
