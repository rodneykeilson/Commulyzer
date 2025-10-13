"""Utilitas dataset untuk pelatihan model toksisitas."""
from __future__ import annotations

from typing import Tuple

import pandas as pd
from datasets import Dataset  # type: ignore


def load_csv_as_dataset(csv_path: str) -> Dataset:
    df = pd.read_csv(csv_path)
    return Dataset.from_pandas(df)


def train_val_split(dataset: Dataset, val_frac: float = 0.1, seed: int = 42) -> Tuple[Dataset, Dataset]:
    if not 0 < val_frac < 1:
        raise ValueError("val_frac harus di antara 0 dan 1")
    dataset = dataset.shuffle(seed=seed)
    val_size = int(len(dataset) * val_frac)
    val_dataset = dataset.select(range(val_size))
    train_dataset = dataset.select(range(val_size, len(dataset)))
    return train_dataset, val_dataset
