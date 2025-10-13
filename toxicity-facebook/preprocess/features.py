"""Ekstraksi fitur sederhana dari teks."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import pandas as pd

from utils.logger import get_logger

LOGGER = get_logger(__name__)


def load_identity_terms(path: str | Path) -> List[str]:
    file_path = Path(path)
    if not file_path.exists():
        LOGGER.warning("identity_terms.txt tidak ditemukan: %s", path)
        return []
    return [line.strip().lower() for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def compute_features(df: pd.DataFrame, identity_terms: List[str]) -> pd.DataFrame:
    df = df.copy()
    df["length_chars"] = df["text_clean"].fillna("").map(len)
    df["num_hashtags"] = df["text"].fillna("").str.count(r"#\w+")
    df["has_url"] = df["text"].fillna("").str.contains(r"https?://", case=False, regex=True)
    df["bag_of_words"] = df["text_clean"].fillna("")

    lower_texts = df["text_clean"].fillna("").str.lower()
    for term in identity_terms:
        column = f"contains_{term.replace(' ', '_')}"
        df[column] = lower_texts.str.contains(term)

    positive_lexicon = {"baik", "positif", "keren", "bagus"}
    negative_lexicon = {"buruk", "toxic", "idiot", "noob", "sampah"}
    df["polarity_score"] = lower_texts.apply(
        lambda text: sum(word in positive_lexicon for word in text.split())
        - sum(word in negative_lexicon for word in text.split())
    )

    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Hitung fitur teks sederhana.")
    parser.add_argument("--in", dest="input_csv", required=True, help="CSV hasil preprocess")
    parser.add_argument("--out", dest="output_csv", required=True, help="Output CSV dengan fitur")
    parser.add_argument("--identity-terms", default="data/identity_terms.txt", help="Daftar istilah identitas")

    args = parser.parse_args()

    df = pd.read_csv(args.input_csv)
    terms = load_identity_terms(args.identity_terms)
    features_df = compute_features(df, terms)
    Path(args.output_csv).parent.mkdir(parents=True, exist_ok=True)
    features_df.to_csv(args.output_csv, index=False)
    LOGGER.info("Fitur tersimpan di %s", args.output_csv)


if __name__ == "__main__":
    main()
