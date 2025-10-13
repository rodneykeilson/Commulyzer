"""Modul pembersihan teks untuk pipeline toksisitas."""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

try:
    import emoji  # type: ignore
except ImportError:  # pragma: no cover
    emoji = None  # type: ignore

from utils.io import read_jsonl
from utils.logger import get_logger

LOGGER = get_logger(__name__)

URL_PATTERN = re.compile(r"https?://\S+")
MENTION_PATTERN = re.compile(r"@[\w_]+")
HASHTAG_PATTERN = re.compile(r"#[\w_]+")
WHITESPACE_PATTERN = re.compile(r"\s+")


def clean_text(text: str, remove_urls: bool = True, remove_mentions: bool = True, lower: bool = True) -> str:
    """Bersihkan teks dari URL, mention, dan normalisasi emoji."""
    if text is None:
        return ""
    processed = html.unescape(text)
    if remove_urls:
        processed = URL_PATTERN.sub("", processed)
    if remove_mentions:
        processed = MENTION_PATTERN.sub("", processed)
    if emoji is not None:
        processed = emoji.demojize(processed, delimiters=(" ", " "))
    processed = processed.replace("&amp;", "dan")
    processed = HASHTAG_PATTERN.sub("", processed)
    processed = WHITESPACE_PATTERN.sub(" ", processed).strip()
    if lower:
        processed = processed.lower()
    return processed


def extract_items_from_raw(
    raw_jsonl_path: str | Path,
    out_csv_path: str | Path,
    sample_comments_per_post: int = 5,
) -> Tuple[int, int]:
    """Ekstrak post dan komentar dari raw JSONL ke CSV datar."""
    raw_data = read_jsonl(raw_jsonl_path)
    posts_written = 0
    comments_written = 0

    out_path = Path(out_csv_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id",
            "parent_post_id",
            "page",
            "type",
            "time",
            "text",
            "text_clean",
            "num_reactions",
            "metadata_json",
        ])
        for post in raw_data:
            text = post.get("text") or ""
            writer.writerow([
                post.get("post_id"),
                "",
                post.get("page"),
                "post",
                post.get("time"),
                text,
                clean_text(text),
                json.dumps(post.get("reactions_summary") or {}),
                json.dumps({k: v for k, v in post.items() if k not in {"text", "comments_sample"}}),
            ])
            posts_written += 1

            comments = post.get("comments_sample") or []
            for comment in comments[:sample_comments_per_post]:
                text_c = comment.get("text") or ""
                writer.writerow([
                    comment.get("comment_id"),
                    post.get("post_id"),
                    post.get("page"),
                    "comment",
                    comment.get("time"),
                    text_c,
                    clean_text(text_c),
                    "0",
                    json.dumps({"source_post": post.get("post_id")}),
                ])
                comments_written += 1

    LOGGER.info("Ekstraksi selesai. Posts: %d, Komentar: %d", posts_written, comments_written)
    return posts_written, comments_written


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Pembersihan teks dan ekstraksi item dari JSONL.")
    parser.add_argument("--in", dest="input_path", required=True, help="Path JSONL raw")
    parser.add_argument("--out", dest="output_path", required=True, help="Path CSV output")
    parser.add_argument("--sample-comments", type=int, default=5, help="Komentar per post")
    parser.add_argument("--fast", action="store_true", help="Mode cepat untuk sample kecil")

    args = parser.parse_args()

    sample_comments = min(args.sample_comments, 10 if args.fast else 50)
    extract_items_from_raw(args.input_path, args.output_path, sample_comments_per_post=sample_comments)


if __name__ == "__main__":
    _cli()
