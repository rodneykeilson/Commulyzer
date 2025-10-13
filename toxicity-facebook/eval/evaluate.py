"""Evaluasi model toksisitas."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List

import pandas as pd
from sklearn.metrics import classification_report  # type: ignore

from train.train_toxicity import predict_texts
from utils.aggregation import aggregate_score_for_query
from utils.logger import get_logger

LOGGER = get_logger(__name__)


def evaluate_model(model_path: str, test_csv: str, query: str, threshold: float, out_dir: Path) -> Dict[str, object]:
    df = pd.read_csv(test_csv)
    predictions = predict_texts(model_path, df["text_clean"].fillna("").tolist())
    scores = predictions["scores"]
    predicted_labels = [1 if score >= threshold else 0 for score in scores]

    report = classification_report(df["label"], predicted_labels, output_dict=True, zero_division=0)

    enriched_rows: List[Dict[str, object]] = []
    for row, score, label in zip(df.to_dict(orient="records"), scores, predicted_labels):
        enriched = dict(row)
        enriched.update({
            "score": score,
            "predicted_label": label,
            "query": query,
        })
        enriched_rows.append(enriched)

    summary = aggregate_score_for_query(enriched_rows, threshold=threshold)
    summary.update({
        "query": query,
        "precision": report["1"].get("precision", 0.0),
        "recall": report["1"].get("recall", 0.0),
        "f1": report["1"].get("f1-score", 0.0),
    })

    out_dir.mkdir(parents=True, exist_ok=True)
    per_item_path = out_dir / f"report_{query.lower().replace(' ', '')}.csv"
    if enriched_rows:
        with per_item_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=enriched_rows[0].keys())
            writer.writeheader()
            writer.writerows(enriched_rows)

    summary_path = out_dir / f"summary_{query.lower().replace(' ', '')}.json"
    with summary_path.open("w", encoding="utf-8") as f:
        import json

        json.dump(summary, f, indent=2, ensure_ascii=False)

    LOGGER.info(
        "Ringkasan evaluasi:\nQuery: %s\nTotal item: %d\nToxic items: %d\nToxic percent: %.2f%%",
        query,
        summary["total_items"],
        summary["toxic_items"],
        summary["toxic_percent"],
    )
    LOGGER.info(
        "Top kata toxic: %s", ", ".join(summary.get("top_toxic_words", []))
    )
    LOGGER.info(
        "Catatan: skor adalah persentase item yang model prediksi toxic (threshold %.2f). Model mungkin bias; lihat docs/ethics.md.",
        threshold,
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluasi model toksisitas pada dataset uji.")
    parser.add_argument("--model_path", required=True, help="Direktori model terlatih")
    parser.add_argument("--test_csv", required=True, help="Dataset uji")
    parser.add_argument("--query", required=True, help="Nama query")
    parser.add_argument("--threshold", type=float, default=0.5, help="Ambang toksisitas")
    parser.add_argument("--out_dir", default="eval", help="Direktori keluaran evaluasi")

    args = parser.parse_args()
    evaluate_model(args.model_path, args.test_csv, args.query, args.threshold, Path(args.out_dir))


if __name__ == "__main__":
    main()
