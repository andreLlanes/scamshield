"""CrewAI tool exposing Agent 2's classifier to the crew.

The pipeline already runs the classifier deterministically for scoring; this
tool lets an agent re-score a *fragment* of the call (a single quoted passage,
for example) while reasoning. Doing so cannot change the final risk score.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.ml.classifier.service import ScamClassifierService

logger = get_logger(__name__)


def build_classifier_tool(classifier: ScamClassifierService) -> Any:
    """Construct the CrewAI tool bound to ``classifier``."""
    from crewai.tools import BaseTool  # noqa: PLC0415  — optional extra
    from pydantic import BaseModel, Field  # noqa: PLC0415

    class _Input(BaseModel):
        text: str = Field(..., description="The passage of call text to score.")

    class ScamClassifierTool(BaseTool):
        name: str = "Scam Text Classifier"
        description: str = (
            "Score a passage of call text with the trained scam classifier. Returns a "
            "scam probability between 0 and 1 and the phrases that drove it. Useful for "
            "checking whether a specific passage reads like a known scam script."
        )
        args_schema: type[BaseModel] = _Input

        def _run(self, text: str) -> str:
            try:
                result = classifier.predict_sync(text)
            except Exception as exc:
                logger.error("classifier_tool_failed", error=str(exc))
                return "Classifier unavailable for this passage."
            drivers = ", ".join(
                f"{feature.feature} ({feature.weight:+.3f})" for feature in result.top_features[:5]
            )
            return (
                f"scam_probability={result.scam_probability:.3f} label={result.label} "
                f"model={result.model_name}\ntop_terms: {drivers or 'none'}"
            )

    return ScamClassifierTool()
