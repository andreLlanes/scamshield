"""Agent 2 — the TF-IDF + XGBoost training pipeline.

Kept separate from the serving code in ``service.py`` so that training can
import scikit-learn/XGBoost freely while the API process only needs joblib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from app.core.logging import get_logger
from app.ml.classifier.preprocessing import clean_text

logger = get_logger(__name__)

ARTIFACT_VERSION = 1


@dataclass
class TrainingMetrics:
    """Held-out performance, saved next to the model for provenance."""

    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float | None
    n_train: int
    n_test: int
    report: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "accuracy": round(self.accuracy, 4),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "roc_auc": round(self.roc_auc, 4) if self.roc_auc is not None else None,
            "n_train": self.n_train,
            "n_test": self.n_test,
        }


@dataclass
class TrainedArtifact:
    """What gets persisted to ``artifacts/scam_classifier.joblib``."""

    pipeline: Pipeline
    metrics: dict[str, Any] = field(default_factory=dict)
    estimator_name: str = "xgboost"
    version: int = ARTIFACT_VERSION


def _build_vectorizer(n_samples: int) -> TfidfVectorizer:
    """Word 1-3 grams: scam signals are phrases ("read me the code"), not words.

    ``min_df=2`` drops n-grams that occur in a single document. On the seed
    corpus that is worth ~7 points of cross-validated accuracy, because most
    trigrams are otherwise singletons the trees can memorise. It is relaxed on
    very small datasets, where it would empty the vocabulary.
    """
    return TfidfVectorizer(
        preprocessor=clean_text,
        ngram_range=(1, 3),
        min_df=2 if n_samples >= 40 else 1,
        max_df=0.9,
        sublinear_tf=True,
        max_features=50_000,
        strip_accents=None,  # clean_text already strips accents
    )


def _build_estimator(n_samples: int) -> tuple[Any, str]:
    """XGBoost when installed, logistic regression otherwise.

    The fallback keeps ``pip install -e .`` (no extras) able to train and serve
    a real model; both expose ``predict_proba`` so serving is unaffected.
    """
    try:
        from xgboost import XGBClassifier  # noqa: PLC0415  — optional extra
    except ImportError:
        logger.warning("xgboost_missing", fallback="logistic_regression")
        return (
            LogisticRegression(max_iter=2000, C=4.0, class_weight="balanced"),
            "logistic_regression",
        )

    # Shallow trees on high-dimensional sparse TF-IDF: depth 3 cross-validated
    # better than depth 5 on the seed corpus and generalises more safely as the
    # dataset grows.
    return (
        XGBClassifier(
            n_estimators=300,
            max_depth=3,
            learning_rate=0.1,
            subsample=0.9,
            colsample_bytree=0.6,
            min_child_weight=1,
            reg_lambda=1.2,
            objective="binary:logistic",
            eval_metric="logloss",
            tree_method="hist",
            n_jobs=-1,
            random_state=42,
        ),
        "xgboost",
    )


def build_pipeline(n_samples: int) -> tuple[Pipeline, str]:
    estimator, name = _build_estimator(n_samples)
    return Pipeline([("tfidf", _build_vectorizer(n_samples)), ("clf", estimator)]), name


def train(
    texts: list[str],
    labels: list[int],
    *,
    test_size: float = 0.2,
    random_state: int = 42,
) -> TrainedArtifact:
    """Fit the pipeline and measure it on a stratified hold-out split."""
    if len(texts) != len(labels):
        raise ValueError("texts and labels must be the same length")
    if len(set(labels)) < 2:
        raise ValueError("Training data must contain both scam (1) and legitimate (0) examples")

    x_train, x_test, y_train, y_test = train_test_split(
        texts, labels, test_size=test_size, random_state=random_state, stratify=labels
    )

    pipeline, estimator_name = build_pipeline(len(texts))
    logger.info("classifier_training", estimator=estimator_name, n_train=len(x_train))
    pipeline.fit(x_train, y_train)

    predictions = pipeline.predict(x_test)
    try:
        probabilities = pipeline.predict_proba(x_test)[:, 1]
        roc_auc = float(roc_auc_score(y_test, probabilities))
    except (AttributeError, ValueError):
        roc_auc = None

    metrics = TrainingMetrics(
        accuracy=float(accuracy_score(y_test, predictions)),
        precision=float(precision_score(y_test, predictions, zero_division=0)),
        recall=float(recall_score(y_test, predictions, zero_division=0)),
        f1=float(f1_score(y_test, predictions, zero_division=0)),
        roc_auc=roc_auc,
        n_train=len(x_train),
        n_test=len(x_test),
        report=classification_report(
            y_test, predictions, target_names=["legitimate", "scam"], zero_division=0
        ),
    )
    logger.info("classifier_trained", **metrics.as_dict())

    # Refit on the full dataset now that the honest estimate is recorded.
    final_pipeline, _ = build_pipeline(len(texts))
    final_pipeline.fit(texts, labels)

    return TrainedArtifact(
        pipeline=final_pipeline,
        metrics={**metrics.as_dict(), "classification_report": metrics.report},
        estimator_name=estimator_name,
    )


def save(artifact: TrainedArtifact, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "version": artifact.version,
            "pipeline": artifact.pipeline,
            "metrics": artifact.metrics,
            "estimator_name": artifact.estimator_name,
        },
        path,
        compress=3,
    )
    logger.info("classifier_saved", path=str(path))
    return path


def load(path: Path) -> TrainedArtifact:
    payload = joblib.load(path)
    if not isinstance(payload, dict) or "pipeline" not in payload:
        raise ValueError(f"{path} is not a ScamShield classifier artifact")
    version = int(payload.get("version", 0))
    if version != ARTIFACT_VERSION:
        logger.warning("classifier_version_mismatch", found=version, expected=ARTIFACT_VERSION)
    return TrainedArtifact(
        pipeline=payload["pipeline"],
        metrics=payload.get("metrics", {}),
        estimator_name=payload.get("estimator_name", "unknown"),
        version=version,
    )


def _is_uninformative(feature: str) -> bool:
    """True for n-grams made entirely of stop words.

    The model is free to lean on ``"and"`` or ``"we"`` — with a small corpus it
    often does — but showing a user "and +0.70" is not an explanation. These
    are filtered from the *display* only; the prediction is untouched.
    """
    tokens = feature.split()
    return bool(tokens) and all(token in ENGLISH_STOP_WORDS for token in tokens)


def explain(pipeline: Pipeline, text: str, *, top_k: int = 8) -> list[tuple[str, float, int]]:
    """Attribute a prediction to individual n-grams.

    Tree models get exact SHAP contributions from XGBoost's ``pred_contribs``;
    linear models get ``coef * tfidf``. Both are signed, so the UI can show
    what pushed *towards* scam and what pushed away from it.
    """
    vectorizer: TfidfVectorizer = pipeline.named_steps["tfidf"]
    estimator = pipeline.named_steps["clf"]

    vector = vectorizer.transform([text])
    if vector.nnz == 0:
        return []

    feature_names = vectorizer.get_feature_names_out()
    present = vector.indices
    values = vector.data
    contributions: dict[int, float] = {}

    booster = getattr(estimator, "get_booster", None)
    if booster is not None:
        try:
            import xgboost as xgb  # noqa: PLC0415  — only present with the ml extra

            matrix = xgb.DMatrix(vector, feature_names=list(feature_names))
            # Last column is the bias term, so drop it.
            shap_values = booster().predict(matrix, pred_contribs=True)[0][:-1]
            contributions = {int(index): float(shap_values[index]) for index in present}
        except Exception as exc:  # pragma: no cover - depends on xgboost build
            logger.debug("shap_unavailable", error=str(exc))

    if not contributions:
        coefficients = getattr(estimator, "coef_", None)
        if coefficients is None:
            return []
        weights = np.asarray(coefficients).ravel()
        contributions = {
            int(index): float(weights[index] * value)
            for index, value in zip(present, values, strict=True)
        }

    ranked = [
        (str(feature_names[index]), round(weight, 5))
        for index, weight in sorted(
            contributions.items(), key=lambda item: abs(item[1]), reverse=True
        )
        if abs(weight) > 1e-6
    ]
    informative = [item for item in ranked if not _is_uninformative(item[0])]
    cleaned = clean_text(text)
    return [
        (feature, weight, max(cleaned.count(feature), 1)) for feature, weight in informative[:top_k]
    ]
