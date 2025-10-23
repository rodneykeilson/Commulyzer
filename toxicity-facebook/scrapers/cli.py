"""CLI untuk scraping toksisitas Facebook."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from collections import defaultdict

from utils.io import read_jsonl
from utils.logger import get_logger

from .facebook_safe import scrape_pages
from .facebook_to_db import load_sample_group_posts, scrape_group_to_db
from .page_discovery import discover_pages_from_keyword

LOGGER = get_logger(__name__)


def _load_pages_file(path: Optional[str]) -> List[str]:
    if not path:
        return []
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File {path} tidak ditemukan")
    return [line.strip() for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _env_allows_scrape() -> bool:
    return os.getenv("ALLOW_SCRAPE", "false").strip().lower() in {"1", "true", "yes"}


def _normalise_group_identifier(value: str) -> str:
    if "facebook.com/groups" in value:
        return value.rstrip("/").split("/")[-1]
    return value.strip()


def _coerce_db_url(raw: str) -> str:
    if not raw:
        raw = "data/toxicity.db"
    if raw.startswith("sqlite://"):
        target = raw.replace("sqlite:///", "", 1)
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        return raw
    if "://" in raw:
        return raw
    path = Path(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.resolve().as_posix()}"


def _build_legacy_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scraper komunitas Facebook yang aman (legacy mode).")
    parser.add_argument("--query", required=True, help="Kata kunci/topik pencarian")
    parser.add_argument("--discover", action="store_true", help="Gunakan discovery halaman otomatis")
    parser.add_argument("--pages-file", dest="pages_file", help="File berisi daftar halaman (satu per baris)")
    parser.add_argument("--max-posts", type=int, default=500, help="Estimasi maksimum post per halaman")
    parser.add_argument("--out", default=None, help="Lokasi file output JSONL")
    parser.add_argument("--delay", type=float, default=1.5, help="Delay antar post dalam detik")
    parser.add_argument("--pages-per-page", type=int, default=5, help="Jumlah halaman yang di-scrape per page")
    parser.add_argument("--options", help="JSON string untuk opsi tambahan facebook_scraper")
    parser.add_argument("--db-url", help="URL database untuk menyimpan hasil (misal sqlite:///toxicity.db)")
    return parser


def _run_legacy_scrape(args: argparse.Namespace) -> None:
    pages: List[str] = []
    if args.discover:
        pages = discover_pages_from_keyword(args.query)

    if args.pages_file:
        pages.extend(_load_pages_file(args.pages_file))

    pages = list(dict.fromkeys(pages))
    if not pages:
        raise SystemExit("Tidak ada halaman untuk di-scrape. Gunakan --discover atau --pages-file.")

    options = json.loads(args.options) if args.options else {}
    out_file = args.out
    if not out_file:
        sanitized = args.query.lower().replace(" ", "")
        out_dir = Path("data/raw")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{sanitized}_raw.jsonl"
    else:
        out_file = Path(out_file)
        out_file.parent.mkdir(parents=True, exist_ok=True)

    rows = scrape_pages(
        pages=pages,
        out_path=str(out_file),
        pages_per_page=args.pages_per_page,
        delay=args.delay,
        options=options,
    )

    if args.db_url:
        from storage.repository import ToxicityRepository

        repo = ToxicityRepository(args.db_url)
        grouped = defaultdict(list)
        for row in rows:
            grouped[row.get("page", "unknown")].append(row)
        total_saved = 0
        for page, page_rows in grouped.items():
            total_saved += repo.save_posts(page, page_rows)
        LOGGER.info("Total tersimpan di database: %d", total_saved)

    rows = read_jsonl(out_file)
    LOGGER.info("Total posts tersimpan: %d", len(rows))
    LOGGER.info("Output disimpan di %s", out_file)


def _build_group_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scrape Facebook group langsung ke database.")
    parser.add_argument("--group", default="mlbbidofficial", help="Identifier group (default: mlbbidofficial)")
    parser.add_argument("--groups-file", help="File teks berisi daftar group (satu per baris)")
    parser.add_argument("--max-posts", type=int, default=100, help="Jumlah maksimal post baru yang disimpan")
    parser.add_argument("--comments-per-post", type=int, default=10, help="Jumlah komentar per post yang disimpan")
    parser.add_argument("--delay", type=float, default=1.5, help="Delay antar permintaan scraping")
    parser.add_argument("--db", default="data/toxicity.db", help="Path atau URL database SQLite")
    parser.add_argument("--cookies", help="Path ke file cookie facebook_scraper (opsional)")
    parser.add_argument("--allow-scrape", action="store_true", help="Konfirmasi eksplisit untuk mengaktifkan scraping jaringan")
    parser.add_argument("--sample-only", action="store_true", help="Gunakan sample JSONL lokal tanpa mengakses jaringan")
    return parser


def _run_group_scrape(args: argparse.Namespace) -> None:
    groups: List[str] = []
    if args.group:
        groups.append(_normalise_group_identifier(args.group))
    if args.groups_file:
        groups.extend(_normalise_group_identifier(item) for item in _load_pages_file(args.groups_file))
    groups = [item for item in groups if item]
    groups = list(dict.fromkeys(groups))
    if not groups:
        raise SystemExit("Masukkan minimal satu group via --group atau --groups-file.")

    db_url = _coerce_db_url(args.db)

    if args.sample_only:
        from storage.repository import ToxicityRepository

        repo = ToxicityRepository(db_url)
        total = 0
        for group in groups:
            sample_rows = load_sample_group_posts(group)
            total += repo.save_posts(group, sample_rows, max_comments=args.comments_per_post)
        LOGGER.info("Mode sample: %d post tersimpan ke %s", total, db_url)
        LOGGER.info("Tidak ada koneksi jaringan yang dilakukan.")
        return

    if not (args.allow_scrape or _env_allows_scrape()):
        raise SystemExit(
            "Scraping jaringan dinonaktifkan secara default. Tambahkan --allow-scrape atau set env ALLOW_SCRAPE=true."
        )

    summaries = []
    for group in groups:
        result = scrape_group_to_db(
            group_identifier=group,
            db_url=db_url,
            max_posts=args.max_posts,
            comments_per_post=args.comments_per_post,
            delay=args.delay,
            cookies_path=args.cookies,
            allow_scrape=True,
        )
        summaries.append(result)
        status = result.get("status")
        if status == "success":
            LOGGER.info(
                "Group %s: tersimpan %d post (percobaan %d).",
                group,
                result.get("posts_saved", 0),
                result.get("attempted", 0),
            )
        else:
            LOGGER.warning("Group %s: %s", group, result.get("message", status))
    LOGGER.info("Ringkasan scrape-group: %s", summaries)


def main(argv: Optional[Sequence[str]] = None) -> None:
    argv = list(argv or sys.argv[1:])
    if argv and argv[0] == "scrape-group":
        parser = _build_group_parser()
        args = parser.parse_args(argv[1:])
        _run_group_scrape(args)
        return

    parser = _build_legacy_parser()
    args = parser.parse_args(argv)
    _run_legacy_scrape(args)


if __name__ == "__main__":
    main()
