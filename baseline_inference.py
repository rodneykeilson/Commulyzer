#!/usr/bin/env python3
"""Standalone helper for running the saved baseline toxicity model."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import joblib
import numpy as np

MODEL_DIR = Path("outputs/models/baseline")


def _normalize_text(text: str | None) -> str:
    if not isinstance(text, str):
        return ""
    cleaned = text.replace("\r", " ").replace("\n", " ")
    return " ".join(cleaned.split()).strip()


def _load_artifacts(model_dir: Path = MODEL_DIR) -> Tuple:
    if not model_dir.exists():
        raise FileNotFoundError(
            f"Baseline artifacts not found at {model_dir}. Run the training notebook first." 
        )
    vectorizer = joblib.load(model_dir / "vectorizer.joblib")
    classifier = joblib.load(model_dir / "ovr_lr.joblib")
    labels = (model_dir / "labels.txt").read_text(encoding="utf-8").splitlines()
    thresholds = json.loads((model_dir / "thresholds.json").read_text(encoding="utf-8"))
    return vectorizer, classifier, labels, thresholds


def _apply_thresholds(probs: np.ndarray, thresholds: dict, labels: Sequence[str]) -> np.ndarray:
    output = np.zeros_like(probs, dtype=int)
    for idx, label in enumerate(labels):
        thr = thresholds.get(label, 0.5)
        output[:, idx] = (probs[:, idx] >= thr).astype(int)
    return output


class BaselineToxicityPredictor:
    """Wraps the saved TF–IDF + logistic regression model for inference."""

    def __init__(self, model_dir: Path = MODEL_DIR):
        self.vectorizer, self.classifier, self.labels, self.thresholds = _load_artifacts(model_dir)

    def predict(self, texts: Sequence[str]) -> Tuple[List[str], np.ndarray, np.ndarray]:
        normalized = [_normalize_text(t) for t in texts]
        features = self.vectorizer.transform(normalized)
        probs = self.classifier.predict_proba(features)
        preds = _apply_thresholds(probs, self.thresholds, self.labels)
        return self.labels, probs, preds


def _format_output(text: str, labels: Sequence[str], probs: np.ndarray, preds: np.ndarray) -> str:
    active = [lab for lab, flag in zip(labels, preds) if flag]
    prob_pairs = ", ".join(f"{lab}:{prob:.3f}" for lab, prob in zip(labels, probs))
    active_display = ", ".join(active) if active else "none"
    return (
        f"TEXT: {text}\n"
        f"Active labels: {active_display}\n"
        f"Probabilities: {prob_pairs}\n"
    )


def run_cli(args: argparse.Namespace) -> None:
    predictor = BaselineToxicityPredictor(Path(args.model_dir))
    labels, probs, preds = predictor.predict(args.text)
    for text, prob_row, pred_row in zip(args.text, probs, preds):
        print(_format_output(text, labels, prob_row, pred_row))
        print("-" * 60)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the saved baseline toxicity model on input text.")
    parser.add_argument(
        "text",
        nargs="+",
        help="One or more strings to score. Enclose multi-word inputs in quotes.",
    )
    parser.add_argument(
        "--model-dir",
        default=str(MODEL_DIR),
        help="Path to the exported baseline artifacts (default: outputs/models/baseline)",
    )
    return parser


if __name__ == "__main__":
    cli_args = build_arg_parser().parse_args()
    run_cli(cli_args)
