#!/usr/bin/env python3
"""Dump the baseline TF–IDF + OvR Logistic Regression model to JSON artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np

ARTIFACT_NAMES = ["vectorizer.joblib", "ovr_lr.joblib", "labels.txt", "thresholds.json"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export baseline model parameters to JSON files.")
    parser.add_argument(
        "--artifacts-dir",
        default="artifacts/baseline",
        help="Directory containing the saved baseline artifacts.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/baseline/json",
        help="Destination directory for the JSON exports.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=50000,
        help="Number of vocabulary entries per shard for readability (default: 50k).",
    )
    return parser.parse_args()


def ensure_artifacts_available(artifacts_dir: Path) -> None:
    missing = [name for name in ARTIFACT_NAMES if not (artifacts_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing artifacts: {missing}")


def export_vectorizer(vectorizer, output_dir: Path, chunk_size: int) -> dict:
    """Serialize TF–IDF parameters and write vocabulary shards."""
    combined_vocab = {}
    info = {
        "ngram_range": vectorizer.ngram_range,
        "min_df": vectorizer.min_df,
        "max_df": vectorizer.max_df,
        "sublinear_tf": vectorizer.sublinear_tf,
        "use_idf": vectorizer.use_idf,
        "norm": vectorizer.norm,
        "lowercase": vectorizer.lowercase,
        "token_pattern": getattr(vectorizer, "token_pattern", None),
    "stop_words": sorted(vectorizer.stop_words) if vectorizer.stop_words is not None else None,
        "binary": vectorizer.binary,
        "smooth_idf": vectorizer.smooth_idf,
        "vocabulary_size": len(vectorizer.vocabulary_),
        "idf": vectorizer.idf_.tolist(),
        "vocabulary_files": [],
    }

    vocab_items = sorted(vectorizer.vocabulary_.items(), key=lambda kv: kv[1])
    for idx, start in enumerate(range(0, len(vocab_items), chunk_size), start=1):
        shard = vocab_items[start : start + chunk_size]
        shard_path = output_dir / f"vocabulary_{idx:03d}.json"
        shard_dict = {term: int(position) for term, position in shard}
        combined_vocab.update(shard_dict)
        shard_path.write_text(json.dumps(shard_dict, ensure_ascii=False), encoding="utf-8")
        info["vocabulary_files"].append(shard_path.name)
    combined_path = output_dir / "vocabulary_combined.json"
    combined_path.write_text(json.dumps(combined_vocab, ensure_ascii=False), encoding="utf-8")
    info["combined_vocabulary"] = combined_path.name
    return info


def export_classifier(classifier, output_dir: Path) -> dict:
    coefs = np.vstack([est.coef_ for est in classifier.estimators_])
    intercepts = np.array([est.intercept_ for est in classifier.estimators_]).reshape(-1)
    coef_path = output_dir / "classifier_coefficients.json"
    intercept_path = output_dir / "classifier_intercepts.json"
    coef_path.write_text(json.dumps(coefs.tolist()), encoding="utf-8")
    intercept_path.write_text(json.dumps(intercepts.tolist()), encoding="utf-8")
    return {
        "coefficients_file": coef_path.name,
        "intercepts_file": intercept_path.name,
        "solver": classifier.estimators_[0].solver,
        "penalty": classifier.estimators_[0].penalty,
        "C": classifier.estimators_[0].C,
        "max_iter": classifier.estimators_[0].max_iter,
        "n_classes": len(classifier.estimators_),
        "n_features": coefs.shape[1],
    }


def main() -> None:
    args = parse_args()
    artifacts_dir = Path(args.artifacts_dir)
    ensure_artifacts_available(artifacts_dir)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    vectorizer = joblib.load(artifacts_dir / "vectorizer.joblib")
    classifier = joblib.load(artifacts_dir / "ovr_lr.joblib")
    labels = (artifacts_dir / "labels.txt").read_text(encoding="utf-8").splitlines()
    thresholds = json.loads((artifacts_dir / "thresholds.json").read_text(encoding="utf-8"))

    vectorizer_info = export_vectorizer(vectorizer, output_dir, args.chunk_size)
    classifier_info = export_classifier(classifier, output_dir)

    metadata = {
        "labels": labels,
        "thresholds": thresholds,
        "vectorizer": vectorizer_info,
        "classifier": classifier_info,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Exported JSON artifacts to {output_dir}")


if __name__ == "__main__":
    main()
