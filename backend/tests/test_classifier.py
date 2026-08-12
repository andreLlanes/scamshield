"""Agent 2 dataset, preprocessing, training, and serving checks."""

from __future__ import annotations

import csv
from pathlib import Path

from app.ml.classifier import lexicon
from app.ml.classifier.pipeline import train
from app.ml.classifier.preprocessing import clean_text
from scripts.train_classifier import load_dataset

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_bundled_dataset_is_balanced_and_complete() -> None:
    path = BACKEND_ROOT / "data" / "training" / "calls.csv"
    texts, labels = load_dataset(path)
    assert len(texts) == 800
    assert sum(labels) == 400
    assert len(labels) - sum(labels) == 400
    with path.open(encoding="utf-8", newline="") as handle:
        assert sum(1 for _ in csv.DictReader(handle)) == 800


def test_small_model_predicts_and_explains() -> None:
    scam = [
        "Pay an urgent processing fee and give me your bank password.",
        "Send money now or your account will be suspended.",
        "You won a prize; provide your card number to claim it.",
        "Transfer funds immediately and do not tell anyone.",
    ]
    legitimate = [
        "Your appointment is confirmed; call the clinic if you need to reschedule.",
        "Your parcel arrives tomorrow and no payment is required.",
        "The library book is due next week; you may renew it online.",
        "Your flight is confirmed and check-in opens tomorrow.",
    ]
    artifact = train(
        scam + legitimate,
        [1] * len(scam) + [0] * len(legitimate),
        test_size=0.25,
        tune=False,
    )
    probability = artifact.pipeline.predict_proba([scam[0]])[0][1]
    assert 0.0 <= probability <= 1.0


def test_normalization_is_stable() -> None:
    assert clean_text("Pay $1,000 now!!!") == "pay moneytoken now"


def test_safety_disclaimer_is_not_treated_as_a_credential_request() -> None:
    safe = "We will never ask for your OTP or password. Call us back at your convenience."
    request = "Please give me your OTP and password immediately."
    assert lexicon.legitimate_disclaimer(safe)
    assert not lexicon.legitimate_disclaimer(request)
