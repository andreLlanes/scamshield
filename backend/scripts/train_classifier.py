"""Train Agent 2's scam classifier.

    python -m scripts.train_classifier
    python -m scripts.train_classifier --data data/training/calls.csv --test-size 0.25

The bundled ``calls.csv`` is generated from the cited 800-transcript Kaggle
dataset. Hyperparameters are tuned only on the training partition; the held-out
partition remains untouched until the final evaluation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
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


def dataset_provenance(path: Path, texts: list[str], labels: list[int]) -> dict[str, object]:
    """Record enough information to trace the exact data used by an artifact."""
    try:
        display_path = str(path.resolve().relative_to(BACKEND_ROOT))
    except ValueError:
        display_path = str(path)
    provenance: dict[str, object] = {
        "path": display_path,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "rows": len(texts),
        "scam_rows": sum(labels),
        "legitimate_rows": len(labels) - sum(labels),
    }
    manifest_path = path.with_name("dataset_manifest.json")
    if manifest_path.exists():
        provenance["manifest"] = json.loads(manifest_path.read_text(encoding="utf-8"))
    return provenance


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
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Where to write the JSON training report (defaults beside the artifact).",
    )
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cv-folds", type=int, default=5)
    parser.add_argument("--search-iterations", type=int, default=20)
    parser.add_argument(
        "--no-tune",
        action="store_true",
        help="Skip hyperparameter search and train with the documented defaults.",
    )
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
        texts,
        labels,
        test_size=args.test_size,
        random_state=args.seed,
        tune=not args.no_tune,
        cv_folds=args.cv_folds,
        search_iterations=args.search_iterations,
        provenance=dataset_provenance(args.data, texts, labels),
    )
    pipeline_module.save(artifact, output)

    metrics = {
        key: value for key, value in artifact.metrics.items() if key != "classification_report"
    }
    report_path = args.report or output.with_name("classifier_training_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_payload = {
        "estimator": artifact.estimator_name,
        "artifact_version": artifact.version,
        "metrics": artifact.metrics,
        "provenance": artifact.provenance,
    }
    report_path.write_text(json.dumps(report_payload, indent=2) + "\n", encoding="utf-8")

    print("\n=== Held-out metrics ===")
    print(json.dumps(metrics, indent=2))
    print(artifact.metrics.get("classification_report", ""))
    print(f"Estimator : {artifact.estimator_name}")
    print(f"Artifact  : {output}")
    print(f"Report    : {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
