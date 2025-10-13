"""Siapkan sampel untuk anotasi manual."""
from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import List

import pandas as pd

from utils.logger import get_logger

LOGGER = get_logger(__name__)


def prepare_annotation(input_csv: str | Path, output_csv: str | Path, sample_size: int = 1000, seed: int = 42) -> int:
    df = pd.read_csv(input_csv)
    if df.empty:
        LOGGER.warning("Dataset kosong, tidak ada sampel.")
        df_sampled = df
    else:
        df_sampled = df.sample(n=min(sample_size, len(df)), random_state=seed)
    df_sampled = df_sampled[["id", "page", "time", "text", "text_clean"]]
    df_sampled["label"] = ""
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    df_sampled.to_csv(output_csv, index=False)
    LOGGER.info("Sampel anotasi disimpan di %s", output_csv)
    return len(df_sampled)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ambil sampel untuk anotasi toksisitas.")
    parser.add_argument("--in", dest="input_csv", required=True, help="CSV hasil preprocess")
    parser.add_argument("--out", dest="output_csv", required=True, help="Lokasi CSV anotasi")
    parser.add_argument("--sample", type=int, default=1000, help="Jumlah sampel")
    parser.add_argument("--seed", type=int, default=42, help="Seed acak")

    args = parser.parse_args()
    prepare_annotation(args.input_csv, args.output_csv, sample_size=args.sample, seed=args.seed)


if __name__ == "__main__":
    main()
