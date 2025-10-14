"""Pipeline satu perintah untuk scraping, penyimpanan, dan prediksi toksisitas.

Contoh: `python -m pipelines.run_pipeline --query "Mobile Legends" --discover --db-url sqlite:///toxicity.db`
"""
from __future__ import annotations

import argparse
import json
from types import SimpleNamespace
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from scrapers.cli import _load_pages_file
from scrapers.facebook_safe import scrape_pages
from scrapers.page_discovery import discover_pages_from_keyword
from preprocess.clean import extract_items_from_raw
from train.train_toxicity import predict_texts, train_model
from utils.aggregation import aggregate_score_for_query
from utils.logger import get_logger
from utils.io import append_jsonl, read_jsonl
from storage.repository import ToxicityRepository

LOGGER = get_logger(__name__)


def _ensure_dir(path: Path) -> None:
    target = path if path.suffix == "" else path.parent
    target.mkdir(parents=True, exist_ok=True)


def _collect_pages(query: str, discover: bool, pages_file: Optional[str], extra_pages: Optional[List[str]]) -> List[str]:
    pages: List[str] = []
    if discover:
        pages.extend(discover_pages_from_keyword(query))
    if pages_file:
        pages.extend(_load_pages_file(pages_file))
    if extra_pages:
        pages.extend(extra_pages)
    pages = [page for page in pages if page]
    pages = list(dict.fromkeys(pages))
    if not pages:
        raise SystemExit("Tidak ada halaman yang ditemukan. Gunakan --pages-file atau --pages.")
    return pages


def _train_if_requested(args: argparse.Namespace) -> None:
    if args.skip_train:
        LOGGER.info("Melewati tahap training sesuai permintaan.")
        return
    LOGGER.info("Memulai pelatihan model toksisitas...")
    namespace = SimpleNamespace(
        train_csv=args.train_csv,
        val_csv=args.val_csv,
        model_name=args.model_name,
        epochs=args.epochs,
        batch_size=args.batch_size,
        max_len=args.max_len,
        output_dir=args.output_dir,
        class_weights=args.class_weights,
        use_weak_labels=False,
        weak_labels_csv=None,
        fast=args.fast,
    )
    train_model(namespace)


def _summarise_predictions(query: str, processed_csv: Path, model_ref: str, threshold: float, out_dir: Path) -> Dict[str, object]:
    df = pd.read_csv(processed_csv)
    if df.empty:
        raise SystemExit("Dataset hasil preprocess kosong, tidak ada yang diprediksi.")
    predictions = predict_texts(model_ref, df["text_clean"].fillna("").tolist())
    records: List[Dict[str, object]] = []
    for row, score, label in zip(df.to_dict(orient="records"), predictions["scores"], predictions["labels"]):
        records.append({
            "post_id": row.get("id"),
            "page": row.get("page"),
            "text": row.get("text"),
            "score": score,
            "predicted_label": label,
            "query": query,
        })
    summary = aggregate_score_for_query(records, threshold=threshold)
    _ensure_dir(out_dir)
    summary_path = out_dir / f"summary_{query.lower().replace(' ', '')}.json"
    import json

    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    narrative = (
        f"Query: \"{query}\"\n"
        f"Total item dianalisis: {summary['total_items']}\n"
        f"Item toxic: {summary['toxic_items']}\n"
        f"Persentase toxic: {summary['toxic_percent']:.1f}%\n"
        f"Top kata toxic: {summary['top_toxic_words']}\n"
        "Catatan: skor adalah persentase item yang model prediksi toxic (threshold 0.5)."
        " Model mungkin bias; lihat docs/ethics.md."
    )
    LOGGER.info("Ringkasan:\n%s", narrative)
    return summary


def run_pipeline(args: argparse.Namespace) -> Dict[str, object]:
    pages = _collect_pages(args.query, args.discover, args.pages_file, args.pages)
    LOGGER.info("Menggunakan halaman: %s", pages)

    sanitized = args.query.lower().replace(" ", "")
    raw_path = Path("data/raw") / f"{sanitized}_pipeline.jsonl"
    processed_path = Path("data/processed") / f"{sanitized}_items.csv"

    options_dict = {}
    if args.options:
        try:
            options_dict = json.loads(args.options)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Gagal membaca opsi JSON: {exc}")

    rows = scrape_pages(
        pages=pages,
        out_path=str(raw_path),
        pages_per_page=args.pages_per_page,
        delay=args.delay,
        options=options_dict,
    )
    if not rows and args.fallback_jsonl:
        LOGGER.warning("Scraping kosong. Menggunakan fallback JSONL %s", args.fallback_jsonl)
        rows = read_jsonl(args.fallback_jsonl)
        if rows:
            append_jsonl(raw_path, rows)
    if not rows:
        raise SystemExit("Scraping tidak menghasilkan data. Pertimbangkan gunakan --fallback-jsonl.")

    if args.db_url:
        repo = ToxicityRepository(args.db_url, echo=args.db_echo)
        from collections import defaultdict

        grouped = defaultdict(list)
        for row in rows:
            grouped[row.get("page", "unknown")].append(row)
        for page, items in grouped.items():
            repo.save_posts(page, items)

    extract_items_from_raw(raw_path, processed_path, sample_comments_per_post=args.sample_comments)
    LOGGER.info("CSV hasil preprocess di %s", processed_path)

    _train_if_requested(args)

    model_ref = args.output_dir
    if args.skip_train and not Path(args.output_dir).exists():
        LOGGER.warning(
            "Model lokal %s tidak ditemukan. Menggunakan model HuggingFace %s untuk prediksi.",
            args.output_dir,
            args.model_name,
        )
        model_ref = args.model_name

    summary = _summarise_predictions(
        query=args.query,
        processed_csv=processed_path,
        model_ref=model_ref,
        threshold=args.threshold,
        out_dir=Path(args.report_dir),
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pipeline lengkap scraping -> storage -> prediksi.")
    parser.add_argument("--query", required=True)
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--pages-file")
    parser.add_argument("--pages", nargs="*", help="Daftar halaman manual")
    parser.add_argument("--max-posts", type=int, default=500)
    parser.add_argument("--pages-per-page", type=int, default=5)
    parser.add_argument("--delay", type=float, default=1.5)
    parser.add_argument("--options", help="JSON string opsi tambahan untuk facebook_scraper")
    parser.add_argument("--sample-comments", type=int, default=5)
    parser.add_argument("--db-url", default="sqlite:///toxicity.db")
    parser.add_argument("--db-echo", action="store_true", help="Aktifkan echo SQLAlchemy")
    parser.add_argument("--fallback-jsonl", help="Gunakan JSONL lokal jika scraping tidak menghasilkan data")
    parser.add_argument("--skip-train", action="store_true")
    parser.add_argument("--train_csv", default="data/sample/train.csv")
    parser.add_argument("--val_csv", default="data/sample/val.csv")
    parser.add_argument("--model_name", default="indolem/indobert-base-p1")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--max_len", type=int, default=128)
    parser.add_argument("--output_dir", default="models/best")
    parser.add_argument("--class_weights", action="store_true")
    parser.add_argument("--fast", action="store_true")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--report_dir", default="reports")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    summary = run_pipeline(args)
    LOGGER.info("Pipeline selesai. Ringkasan: %s", summary)


if __name__ == "__main__":
    main()
