"""Convert the original two-file Kaggle corpus into ScamShield's CSV schema.

Expected input files:
  - English_Scam.txt
  - English_NonScam.txt

Each blank-line-delimited block is one transcript. The scam source uses list
ordinals (``1.`` through ``400.``); those presentation-only prefixes are removed
so the classifier cannot learn that numbering is a scam signal.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

DATASET_URL = (
    "https://www.kaggle.com/datasets/teeconnie/"
    "scam-and-non-scam-call-conversation-dataset"
)
DATASET_DOI = "10.34740/KAGGLE/DSV/11606256"
DATASET_LICENSE = "CC BY-NC-ND 4.0"
PAPER_URL = "https://doi.org/10.1109/ACCESS.2025.3582661"
_ORDINAL = re.compile(r"^\s*\d+\.\s*", re.DOTALL)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_transcripts(path: Path, *, remove_ordinals: bool = False) -> list[str]:
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    transcripts = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if remove_ordinals:
        transcripts = [_ORDINAL.sub("", item, count=1).strip() for item in transcripts]
    return transcripts


def build_dataset(
    scam_path: Path,
    legitimate_path: Path,
    output_path: Path,
    manifest_path: Path,
    *,
    expected_per_class: int = 400,
) -> None:
    scam = read_transcripts(scam_path, remove_ordinals=True)
    legitimate = read_transcripts(legitimate_path)
    counts = {"scam": len(scam), "legitimate": len(legitimate)}
    if counts != {"scam": expected_per_class, "legitimate": expected_per_class}:
        raise ValueError(
            f"Expected {expected_per_class} transcripts per class, found {counts}"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["label", "category", "text"])
        writer.writeheader()
        writer.writerows(
            {"label": "scam", "category": "kaggle_scam", "text": text}
            for text in scam
        )
        writer.writerows(
            {"label": "legitimate", "category": "kaggle_non_scam", "text": text}
            for text in legitimate
        )

    manifest = {
        "dataset": "Scam and Non-Scam Call Conversation Dataset",
        "creators": ["Brendan Hong Jun Zhi", "Tee Connie"],
        "source_url": DATASET_URL,
        "dataset_doi": DATASET_DOI,
        "license": DATASET_LICENSE,
        "related_paper": PAPER_URL,
        "rows": len(scam) + len(legitimate),
        "class_counts": counts,
        "unique_transcript_counts": {
            "scam": len(set(scam)),
            "legitimate": len(set(legitimate)),
        },
        "processing": [
            "Split blank-line-delimited transcript blocks",
            "Removed numeric list ordinals from scam entries",
            "Added label and source-category columns",
        ],
        "source_sha256": {
            scam_path.name: _sha256(scam_path),
            legitimate_path.name: _sha256(legitimate_path),
        },
        "output_sha256": _sha256(output_path),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare Agent 2's Kaggle dataset")
    default_raw = Path(__file__).resolve().parents[1] / "data" / "training" / "raw"
    parser.add_argument("--scam-file", type=Path, default=default_raw / "English_Scam.txt")
    parser.add_argument(
        "--non-scam-file", type=Path, default=default_raw / "English_NonScam.txt"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_raw.parent / "calls.csv",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=default_raw.parent / "dataset_manifest.json",
    )
    parser.add_argument("--expected-per-class", type=int, default=400)
    args = parser.parse_args()

    build_dataset(
        args.scam_file,
        args.non_scam_file,
        args.output,
        args.manifest,
        expected_per_class=args.expected_per_class,
    )
    print(f"Wrote {args.output} and {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
