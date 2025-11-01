#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rule-based multilabel annotator for Reddit comments.

This script scores each comment against six toxicity dimensions plus racism, using
regex libraries sourced from TSV files and a negation-aware severity formula. It
emits both severity scores (0..1) and binary flags for every label, plus a joined
"labels" column for quick inspection. Usage examples:

    python label-comments.py --input data/processed/merged/merged_comments.csv --output data/processed/labeled/labeled_comments.csv
    python label-comments.py --input ... --output ... --threshold 0.4
    python label-comments.py --input ... --pattern-dir patterns --extra-patterns-dir custom

All regex lists contain offensive language purely for detection purposes.
"""

from __future__ import annotations
import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
from tqdm import tqdm


# -----------------------------
# Config
# -----------------------------
LABELS = [
    "toxic",
    "severe_toxic",
    "obscene",
    "threat",
    "insult",
    "identity_hate",
    "racism",
]

DEFAULT_PATTERN_DIR = Path(__file__).resolve().parent / "patterns"

# Negation tokens and window (in tokens) to suppress false positives like "not stupid"
NEGATORS = {
    "not", "no", "never", "aint", "ain't", "isnt", "isn't", "arent", "aren't",
    "dont", "don't", "didnt", "didn't", "cant", "can't", "cannot", "won't", "wont",
    "without", "hardly", "barely", "scarcely"
}
NEGATION_WINDOW = 3  # tokens to the left

# Default threshold for converting severity score to binary 0/1
DEFAULT_BIN_THRESHOLD = 0.5

# Max score cap per label (prevents runaway totals)
MAX_SCORE_PER_LABEL = 1.0

# Normalization factors for scoring (tune-able)
COUNT_WEIGHT = 0.50
INTENSITY_WEIGHT = 0.15


@dataclass
class PatternSpec:
    """Compiled regex and its base intensity weight (>=1)"""
    regex: re.Pattern
    intensity: float
    # whether to require whole-word like boundaries — already baked into patterns usually
    # but you can use this flag to do custom checks if desired.


# -----------------------------
# Pattern library loading helpers (TSV-based)
# Slurs and insults are included SOLELY for detection purposes.
# Patterns live under patterns/<label>.tsv and can be extended safely.
# -----------------------------


def load_pattern_file(filepath: Path) -> List[PatternSpec]:
    specs: List[PatternSpec] = []
    text = filepath.read_text(encoding="utf-8")
    for idx, raw in enumerate(text.splitlines()):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "\t" not in line and "\\t" in line:
            line = line.replace("\\t", "\t")
        parts = line.split("\t")
        if len(parts) == 1:
            pattern, weight = parts[0], 1.0
        else:
            pattern, weight = parts[0], float(parts[1] or 1.0)
        try:
            specs.append(PatternSpec(re.compile(pattern, re.IGNORECASE), weight))
        except re.error as exc:
            raise ValueError(f"Invalid regex in {filepath.name}:{idx + 1}: {exc}") from exc
    return specs


def load_pattern_dir(dirpath: Path, allow_missing: bool = False) -> Dict[str, List[PatternSpec]]:
    out: Dict[str, List[PatternSpec]] = {}
    for label in LABELS:
        fp = dirpath / f"{label}.tsv"
        if not fp.exists():
            if allow_missing:
                continue
            raise FileNotFoundError(f"Pattern file missing: {fp}")
        specs = load_pattern_file(fp)
        if specs:
            out[label] = specs
    return out


# -----------------------------
# Core
# -----------------------------
TOKEN_SPLIT = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def tokenize(text: str) -> List[str]:
    return TOKEN_SPLIT.findall(text.lower())


def has_negation(tokens: List[str], idx_start: int) -> bool:
    """
    Check if any negator appears within NEGATION_WINDOW tokens BEFORE idx_start.
    idx_start is an approximate start token index of matched phrase.
    """
    left = max(0, idx_start - NEGATION_WINDOW)
    for t in tokens[left:idx_start]:
        if t in NEGATORS:
            return True
    return False


def match_with_negation(text: str, tokens: List[str], patterns: List[PatternSpec]) -> Tuple[int, float]:
    """
    Return (count_matches, total_intensity) after applying negation sensitivity.
    We estimate token start index via a second pass: take the start char index and map to token index.
    """
    count = 0   
    intensity_sum = 0.0

    # Map char positions to token indices to approximate start index
    pos_to_tok = []
    cur = 0
    for i, tok in enumerate(tokens):
        # find tok in text starting from cur
        j = text.lower().find(tok, cur)
        if j < 0:
            # fallback: keep same cur
            pos_to_tok.append((i, cur))
        else:
            pos_to_tok.append((i, j))
            cur = j + len(tok)

    for spec in patterns:
        for m in spec.regex.finditer(text):
            start = m.start()
            # approximate token index: nearest token whose start pos <= start
            tok_idx = 0
            for i, pos in pos_to_tok:
                if pos <= start:
                    tok_idx = i
                else:
                    break
            if not has_negation(tokens, tok_idx):
                count += 1
                intensity_sum += spec.intensity

    return count, intensity_sum


def score_label(text: str, tokens: List[str], patterns: List[PatternSpec]) -> float:
    matches, intensity = match_with_negation(text, tokens, patterns)
    raw = COUNT_WEIGHT * matches + INTENSITY_WEIGHT * intensity
    return min(MAX_SCORE_PER_LABEL, raw)


def annotate_text(text: str, patterns_all: Dict[str, List[PatternSpec]]) -> Dict[str, float]:
    if not isinstance(text, str):
        text = ""
    stripped = text.strip()
    if stripped == "" or stripped.lower().startswith("http"):
        return {f"{lab}_score": 0.0 for lab in LABELS}

    tokens = tokenize(stripped)

    scores = {}
    # compute per-label score
    for lab in LABELS:
        pat = patterns_all.get(lab, [])
        scores[f"{lab}_score"] = score_label(stripped, tokens, pat)

    # Ensure baseline toxic label mirrors stronger classes so single insults count as toxic
    co = ["severe_toxic", "threat", "obscene", "insult", "identity_hate", "racism"]
    max_co = max(scores[f"{c}_score"] for c in co)
    scores["toxic_score"] = max(scores["toxic_score"], max_co)

    return scores


def to_binary(scores: Dict[str, float], threshold: float) -> Dict[str, int]:
    bins = {}
    for lab in LABELS:
        bins[f"{lab}_bin"] = 1 if scores[f"{lab}_score"] >= threshold else 0
    return bins


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="input CSV path (must contain 'body' column)")
    ap.add_argument("--output", help="output CSV path (default: append _labeled)")
    ap.add_argument("--inplace", action="store_true", help="overwrite the input file")
    ap.add_argument("--threshold", type=float, default=DEFAULT_BIN_THRESHOLD, help="binary threshold for *_score (default: 0.5)")
    ap.add_argument("--pattern-dir", type=str, default=None, help="base pattern directory (defaults to patterns/ next to this script)")
    ap.add_argument("--extra-patterns-dir", type=str, default=None, help="optional dir containing <label>.tsv with extra regexes")
    args = ap.parse_args()

    inp = Path(args.input)
    out = Path(args.output) if args.output else Path(inp.parent, inp.stem + "_labeled" + inp.suffix)
    if args.inplace:
        out = inp

    if not inp.exists():
        raise FileNotFoundError(inp)

    print(f"Reading {inp} ...")
    df = pd.read_csv(inp, dtype=str, keep_default_na=False)
    if "body" not in df.columns:
        raise ValueError(f"Expected 'body' column. Found: {df.columns.tolist()}")

    # Build pattern library (TSV-based)
    base_pattern_dir = Path(args.pattern_dir).expanduser() if args.pattern_dir else DEFAULT_PATTERN_DIR
    if not base_pattern_dir.exists():
        raise FileNotFoundError(f"Pattern directory not found: {base_pattern_dir}")
    patterns_all = load_pattern_dir(base_pattern_dir)
    print(f"Loaded base patterns from {base_pattern_dir}")

    # Optional: extend via external TSV pattern files
    if args.extra_patterns_dir:
        extra_dir = Path(args.extra_patterns_dir)
        if extra_dir.exists():
            extra = load_pattern_dir(extra_dir, allow_missing=True)
            for lab, specs in extra.items():
                patterns_all.setdefault(lab, []).extend(specs)
            print(f"Loaded extra patterns from {extra_dir}")
        else:
            print(f"[WARN] extra patterns dir not found: {extra_dir}")

    # Prepare output columns
    for lab in LABELS:
        df[f"{lab}_score"] = 0.0
        df[f"{lab}_bin"] = 0
    df["labels"] = ""

    print("Annotating rows (negation-aware, severity scoring)...")
    for i, txt in enumerate(tqdm(df["body"], total=len(df))):
        scores = annotate_text(txt, patterns_all)
        bins = to_binary(scores, args.threshold)

        # write scores/bins
        for k, v in scores.items():
            df.at[i, k] = round(float(v), 4)
        for k, v in bins.items():
            df.at[i, k] = int(v)

        # build labels string (only for labels that passed threshold)
        active = [lab for lab in LABELS if df.at[i, f"{lab}_bin"] == 1]
        df.at[i, "labels"] = "|".join(active)

    print(f"Writing output to {out} ...")
    df.to_csv(out, index=False, quoting=csv.QUOTE_MINIMAL)

    # Simple stats
    print("\nLabel counts (binary, threshold >= {:.2f}):".format(args.threshold))
    for lab in LABELS:
        c = int(df[f"{lab}_bin"].sum())
        print(f"  {lab:14s}: {c}")

    source_col = "source_subreddit" if "source_subreddit" in df.columns else None
    total_rows = len(df)
    toxic_rows = int(df["toxic_bin"].sum())
    clean_rows = total_rows - toxic_rows
    toxic_pct = (toxic_rows / total_rows * 100) if total_rows else 0.0
    print(f"\nOverall toxic rows: {toxic_rows}/{total_rows} ({toxic_pct:.2f}%)")
    print(f"Overall non-toxic rows: {clean_rows}/{total_rows} ({100 - toxic_pct:.2f}%)")

    if source_col:
        print("\nPer-subreddit stats:")
        grouped = df.groupby(source_col, sort=True)
        for subreddit, grp in grouped:
            size = len(grp)
            tox = int(grp["toxic_bin"].sum())
            clean = size - tox
            pct = (tox / size * 100) if size else 0.0
            print(f"  r/{subreddit}: {tox}/{size} toxic ({pct:.2f}%), {clean} clean")
            for lab in LABELS:
                if lab == "toxic":
                    continue
                lab_count = int(grp[f"{lab}_bin"].sum())
                if lab_count:
                    print(f"    {lab:14s}: {lab_count}")

    print("\nDone.")


if __name__ == "__main__":
    main()
