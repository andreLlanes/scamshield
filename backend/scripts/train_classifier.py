"""Train Agent 2's scam classifier.

    python -m scripts.train_classifier
    python -m scripts.train_classifier --data data/training/calls.csv --test-size 0.25

The bundled dataset in ``data/training/calls.csv`` is a small seed corpus meant
to make the pipeline demonstrable end to end. Point ``--data`` at a larger
labelled corpus before quoting any accuracy number as meaningful.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.ml.classifier import pipeline as pipeline_module  # noqa: E402

logger = get_logger("train_classifier")

_SCAM_LABELS = {"scam", "1", "true", "fraud"}
_LEGIT_LABELS = {"legit", "legitimate", "0", "false", "ham"}


def load_dataset(path: Path) -> tuple[list[str], list[int]]:
    """Read a ``label,category,text`` CSV into parallel text/label lists."""
    if not path.exists():
        raise FileNotFoundError(f"Training data not found: {path}")

    texts: list[str] = []
    labels: list[int] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "text" not in reader.fieldnames:
            raise ValueError(f"{path} must have a 'text' column; found {reader.fieldnames}")
        for row_number, row in enumerate(reader, start=2):
            text = (row.get("text") or "").strip()
            raw_label = (row.get("label") or "").strip().lower()
            if not text:
                continue
            if raw_label in _SCAM_LABELS:
                labels.append(1)
            elif raw_label in _LEGIT_LABELS:
                labels.append(0)
            else:
                logger.warning("skipping_row", row=row_number, label=raw_label)
                continue
            texts.append(text)

    if not texts:
        raise ValueError(f"No usable rows in {path}")
    return texts, labels


def main() -> int:
    settings = get_settings()
    configure_logging(settings)

    parser = argparse.ArgumentParser(description="Train the ScamShield scam classifier")
    parser.add_argument(
        "--data",
        type=Path,
        default=BACKEND_ROOT / "data" / "training" / "calls.csv",
        help="Labelled CSV with 'label' and 'text' columns.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Where to write the joblib artifact (defaults to the configured path).",
    )
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    output = args.output or settings.resolve(settings.classifier_model_path)

    texts, labels = load_dataset(args.data)
    logger.info(
        "dataset_loaded",
        rows=len(texts),
        scam=sum(labels),
        legitimate=len(labels) - sum(labels),
        source=str(args.data),
    )

    artifact = pipeline_module.train(
        texts, labels, test_size=args.test_size, random_state=args.seed
    )
    pipeline_module.save(artifact, output)

    metrics = {
        key: value for key, value in artifact.metrics.items() if key != "classification_report"
    }
    print("\n=== Held-out metrics ===")
    print(json.dumps(metrics, indent=2))
    print(artifact.metrics.get("classification_report", ""))
    print(f"Estimator : {artifact.estimator_name}")
    print(f"Artifact  : {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
