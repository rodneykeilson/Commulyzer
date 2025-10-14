"""CLI untuk scraping toksisitas Facebook."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Optional

from collections import defaultdict

from utils.io import read_jsonl
from utils.logger import get_logger

from .facebook_safe import scrape_pages
from .page_discovery import discover_pages_from_keyword

LOGGER = get_logger(__name__)


def _load_pages_file(path: Optional[str]) -> List[str]:
    if not path:
        return []
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File {path} tidak ditemukan")
    return [line.strip() for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Scraper komunitas Facebook yang aman.")
    parser.add_argument("--query", required=True, help="Kata kunci/topik pencarian")
    parser.add_argument("--discover", action="store_true", help="Gunakan discovery halaman otomatis")
    parser.add_argument("--pages-file", dest="pages_file", help="File berisi daftar halaman (satu per baris)")
    parser.add_argument("--max-posts", type=int, default=500, help="Estimasi maksimum post per halaman")
    parser.add_argument("--out", default=None, help="Lokasi file output JSONL")
    parser.add_argument("--delay", type=float, default=1.5, help="Delay antar post dalam detik")
    parser.add_argument("--pages-per-page", type=int, default=5, help="Jumlah halaman yang di-scrape per page")
    parser.add_argument("--options", help="JSON string untuk opsi tambahan facebook_scraper")
    parser.add_argument("--db-url", help="URL database untuk menyimpan hasil (misal sqlite:///toxicity.db)")

    args = parser.parse_args()

    pages: List[str] = []
    if args.discover:
        pages = discover_pages_from_keyword(args.query)

    if args.pages_file:
        pages.extend(_load_pages_file(args.pages_file))

    pages = list(dict.fromkeys(pages))  # dedup sambil preserve urutan
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


if __name__ == "__main__":
    main()
