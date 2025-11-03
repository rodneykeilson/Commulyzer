#!/usr/bin/env python3
"""Merge all subreddit comment CSVs into a single aggregate file."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import pandas as pd

DATA_ROOT = Path(__file__).resolve().parent / "data" / "raw" / "reddit"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "data" / "processed" / "merged" / "merged_comments.csv"


def find_comment_files(root: Path) -> List[Path]:
    if not root.exists():
        raise FileNotFoundError(f"Input directory does not exist: {root}")
    return sorted(p for p in root.glob("**/comments.csv") if p.is_file())


def merge_comment_csv(files: List[Path], root: Path) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    for path in files:
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        try:
            rel = path.relative_to(root)
            source = rel.parts[0] if rel.parts else path.parent.name
        except ValueError:
            source = path.parent.name if path.parent != path else str(path)
        df.insert(0, "source_subreddit", source)
        frames.append(df)
    if not frames:
        raise ValueError("No comments.csv files found to merge.")
    return pd.concat(frames, ignore_index=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge subreddit comments CSV files into one dataset.")
    parser.add_argument(
        "--input-root",
        type=Path,
        default=DATA_ROOT,
        help="Root directory containing subreddit folders (default: data/raw/reddit).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Destination CSV path (default: data/processed/merged/merged_comments.csv).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    comment_files = find_comment_files(args.input_root)
    if not comment_files:
        raise SystemExit(f"No comments.csv files found under {args.input_root}")

    merged = merge_comment_csv(comment_files, args.input_root)

    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    print(f"Merged {len(comment_files)} files ({len(merged):,} rows) into {output_path}")


if __name__ == "__main__":
    main()
