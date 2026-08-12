"""Agent 2 serving layer — scam probability for a transcript."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import anyio

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.ml.classifier import lexicon
from app.ml.classifier import pipeline as pipeline_module
from app.schemas.classification import ClassificationResult, FeatureContribution

logger = get_logger(__name__)

# Tree ensembles can produce a confident intercept-driven prediction even when
# none of the input n-grams contributed meaningfully. Below this attribution
# mass, use the conservative phrase scorer instead of presenting an unsupported
# probability as model evidence.
_MIN_ATTRIBUTION_MASS = 0.15


class ScamClassifierService:
    """Loads the trained artifact once; degrades to the lexicon scorer."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._artifact: pipeline_module.TrainedArtifact | None = None
        self._load_attempted = False

    @property
    def model_path(self) -> Path:
        return self._settings.resolve(self._settings.classifier_model_path)

    def _ensure_loaded(self) -> pipeline_module.TrainedArtifact | None:
        if self._load_attempted:
            return self._artifact
        self._load_attempted = True

        path = self.model_path
        if not path.exists():
            logger.warning(
                "classifier_artifact_missing",
                path=str(path),
                hint="Run: python -m scripts.train_classifier",
            )
            return None
        try:
            self._artifact = pipeline_module.load(path)
            logger.info(
                "classifier_loaded",
                estimator=self._artifact.estimator_name,
                metrics=self._artifact.metrics.get("f1"),
            )
        except Exception as exc:
            logger.error("classifier_load_failed", error=str(exc), path=str(path))
            self._artifact = None
        return self._artifact

    def is_ready(self) -> bool:
        return self._ensure_loaded() is not None

    def describe(self) -> dict[str, object]:
        artifact = self._ensure_loaded()
        if artifact is None:
            return {"model": "lexicon-fallback", "trained": False}
        return {
            "model": f"tfidf+{artifact.estimator_name}",
            "trained": True,
            "metrics": artifact.metrics,
            "provenance": artifact.provenance,
        }

    def reload(self) -> None:
        """Drop the cached artifact so the next call picks up a retrained model."""
        self._artifact = None
        self._load_attempted = False

    # ---- Prediction -------------------------------------------------------
    def predict_sync(self, text: str) -> ClassificationResult:
        artifact = self._ensure_loaded()
        if artifact is None:
            return self._fallback(text)

        try:
            probability = float(artifact.pipeline.predict_proba([text])[0][1])
            features = pipeline_module.explain(artifact.pipeline, text)
            lexicon_probability, lexicon_hits = lexicon.score(text)
            attribution_mass = sum(abs(weight) for _, weight, _ in features)
            evidence_gate = attribution_mass < _MIN_ATTRIBUTION_MASS
            if evidence_gate:
                probability = lexicon_probability
                existing = {name for name, _, _ in features}
                lexicon_features = [
                    (hit.entry.phrase, hit.entry.weight, hit.occurrences)
                    for hit in lexicon_hits
                    if hit.entry.phrase not in existing
                ]
                features = (lexicon_features + features)[:8]
            elif lexicon.legitimate_disclaimer(text, lexicon_hits):
                probability = min(probability, lexicon_probability)
                existing = {name for name, _, _ in features}
                disclaimer_features = [
                    (hit.entry.phrase, hit.entry.weight, hit.occurrences)
                    for hit in lexicon_hits
                    if hit.entry.weight < 0 and hit.entry.phrase not in existing
                ]
                features = (disclaimer_features + features)[:8]
        except Exception as exc:
            logger.error("classifier_predict_failed", error=str(exc))
            return self._fallback(text)

        return ClassificationResult(
            scam_probability=round(probability, 4),
            label="scam" if probability >= 0.5 else "legitimate",
            model_name=f"tfidf+{artifact.estimator_name}",
            is_fallback=False,
            top_features=[
                FeatureContribution(feature=name, weight=weight, occurrences=count)
                for name, weight, count in features
            ],
        )

    async def predict(self, text: str) -> ClassificationResult:
        """Run inference in a worker thread (tree models release the GIL poorly)."""
        return await anyio.to_thread.run_sync(self.predict_sync, text)

    def _fallback(self, text: str) -> ClassificationResult:
        probability, hits = lexicon.score(text)
        return ClassificationResult(
            scam_probability=probability,
            label="scam" if probability >= 0.5 else "legitimate",
            model_name="lexicon-fallback",
            is_fallback=True,
            top_features=[
                FeatureContribution(
                    feature=hit.entry.phrase,
                    weight=hit.entry.weight,
                    occurrences=hit.occurrences,
                )
                for hit in hits[:8]
            ],
        )


@lru_cache(maxsize=1)
def get_classifier_service() -> ScamClassifierService:
    return ScamClassifierService()
