"""Explainability untuk model toksisitas."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

from train.train_toxicity import predict_texts
from utils.logger import get_logger

LOGGER = get_logger(__name__)

try:
    import shap  # type: ignore
except ImportError:  # pragma: no cover
    shap = None


def explain_texts(model_path: str, texts: List[str], out_dir: Path) -> None:
    if shap is None:
        LOGGER.warning("SHAP tidak tersedia. Lewati explainability.")
        return
    from transformers import AutoModelForSequenceClassification, AutoTokenizer  # type: ignore
    import torch  # type: ignore

    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path)
    model.eval()

    def f(batch):
        with torch.no_grad():
            inputs = tokenizer(batch, padding=True, truncation=True, return_tensors="pt")
            outputs = model(**inputs)
            scores = torch.softmax(outputs.logits, dim=-1).numpy()
        return scores

    explainer = shap.Explainer(f, tokenizer)
    shap_values = explainer(texts)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / "shap_summary.html"
    shap.plots.text(shap_values, display=False)
    shap.save_html(str(output_path), shap_values)
    LOGGER.info("Explainability SHAP tersimpan di %s", output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate explainability untuk contoh toksisitas.")
    parser.add_argument("--model_path", required=True)
    parser.add_argument("--csv", required=True)
    parser.add_argument("--out_dir", default="eval/explain")
    parser.add_argument("--top_n", type=int, default=10)

    args = parser.parse_args()
    df = pd.read_csv(args.csv)
    if "score" in df.columns:
        df_sorted = df.sort_values("score", ascending=False)
    else:
        predictions = predict_texts(args.model_path, df["text_clean"].fillna("").tolist())
        df["score"] = predictions["scores"]
        df_sorted = df.sort_values("score", ascending=False)

    texts = df_sorted["text_clean"].fillna("").tolist()[: args.top_n]
    explain_texts(args.model_path, texts, Path(args.out_dir))


if __name__ == "__main__":
    main()
