# Agent 2 training data

`calls.csv` contains 800 English call transcripts: 400 scam and 400 legitimate.
It was prepared from Brendan Hong Jun Zhi and Tee Connie's **Scam and Non-Scam
Call Conversation Dataset**, available on
[Kaggle](https://www.kaggle.com/datasets/teeconnie/scam-and-non-scam-call-conversation-dataset)
(dataset DOI: `10.34740/KAGGLE/DSV/11606256`). The source is marked
**CC BY-NC-ND 4.0** and is intended for academic, research, and educational use.

The two downloaded source files are retained verbatim under `raw/`. The CSV is a
mechanical training representation: blank-line blocks become rows, numeric list
ordinals are removed from scam entries to prevent label leakage, and label/source
columns are added. `dataset_manifest.json` records counts, exact-duplicate counts,
and SHA-256 checksums. Training uses group-aware splits, keeping exact duplicate
transcripts in one partition so they cannot leak into the held-out evaluation.

Rebuild the CSV and retrain the tuned model from `backend/`:

```bash
python -m scripts.prepare_kaggle_dataset
python -m scripts.train_classifier
```

The supplied 2026 robocall paper,
[Altwlkany et al.](https://arxiv.org/abs/2606.31790), motivates international and
multilingual evaluation. Its released transcript set is robocall-only, so it is
not merged into this balanced scam/non-scam classifier corpus.
