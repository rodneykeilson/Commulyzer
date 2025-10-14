"""Scraper Facebook dengan perhatian privasi.

Catatan: facebook_scraper memungkinkan penggunaan cookie untuk akses konten
lebih banyak. Simpan cookie di berkas `.env` (lihat README) dan jangan pernah
commit kredensial. Library ini memiliki batasan; scraping intensif dapat
melanggar ToS Facebook. Gunakan hanya untuk studi terbatas.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from utils.logger import get_logger

LOGGER = get_logger(__name__)

try:
    from facebook_scraper import get_posts  # type: ignore
except ImportError:  # pragma: no cover - fallback otomatis
    get_posts = None  # type: ignore


def _serialize_post(post: Dict[str, object], page: str, max_comments: int) -> Dict[str, object]:
    """Normalisasi struktur post."""
    comments_sample = []
    raw_comments = post.get("comments_full") or post.get("comments") or []
    for comment in raw_comments[:max_comments]:
        comments_sample.append({
            "comment_id": comment.get("comment_id"),
            "text": comment.get("comment_text"),
            "time": comment.get("comment_time").isoformat() if comment.get("comment_time") else None,
        })

    reactions_summary = post.get("reactions") or post.get("reactions_full") or {}
    if isinstance(reactions_summary, list):
        reactions_summary = {item.get("type", "unknown"): item.get("count", 0) for item in reactions_summary}

    return {
        "post_id": post.get("post_id"),
        "page": page,
        "time": post.get("time").isoformat() if post.get("time") else None,
        "text": post.get("text"),
        "comments_count": post.get("comments"),
        "reactions_summary": reactions_summary,
        "fetched_time": datetime.now(tz=timezone.utc).isoformat(),
        "comments_sample": comments_sample,
    }


def _fallback_scrape(page: str, pages_per_page: int) -> List[Dict[str, object]]:
    """Fallback sederhana menggunakan snscrape jika facebook_scraper tidak tersedia."""
    try:
        from snscrape.modules.facebook import FacebookPageScraper  # type: ignore
    except ImportError:  # pragma: no cover
        LOGGER.error("snscrape tidak tersedia. Mohon install atau siapkan data manual.")
        return []

    LOGGER.info("Menggunakan fallback snscrape untuk halaman %s", page)
    scraper = FacebookPageScraper(page)
    results = []
    for idx, item in enumerate(scraper.get_posts_pages(pages_per_page)):
        if idx >= pages_per_page:
            break
        processed = {
            "post_id": item.post_id,
            "page": page,
            "time": item.date.isoformat() if item.date else None,
            "text": item.content,
            "comments_count": None,
            "reactions_summary": {},
            "fetched_time": datetime.now(tz=timezone.utc).isoformat(),
            "comments_sample": [],
        }
        results.append(processed)
    return results


def scrape_pages(
    pages: List[str],
    out_path: str,
    pages_per_page: int = 5,
    delay: float = 1.5,
    options: Optional[Dict[str, object]] = None,
) -> List[Dict[str, object]]:
    """Scrape daftar halaman secara aman.

    Parameter options dapat berisi cookie_path dan limit komentar.
    """
    max_comments = 10
    if options and isinstance(options.get("comments"), int):
        max_comments = min(int(options["comments"]), 50)

    rows: List[Dict[str, object]] = []

    if get_posts is None:
        LOGGER.warning("facebook_scraper tidak tersedia. Menggunakan fallback.")
        for page in pages:
            rows.extend(_fallback_scrape(page, pages_per_page))
        _dump_jsonl(out_path, rows)
        return rows

    cookie_file = options.get("cookies") if options else None
    if cookie_file and not os.path.exists(cookie_file):
        LOGGER.warning("Cookie file %s tidak ditemukan, lanjut tanpa cookie", cookie_file)
        cookie_file = None

    for page in pages:
        LOGGER.info("Memulai scraping untuk halaman %s", page)
        try:
            posts_iter = get_posts(
                page,
                pages=pages_per_page,
                options={k: v for k, v in (options or {}).items() if k != "cookies"},
                cookies=cookie_file,
            )
        except Exception as exc:  # pragma: no cover - library eksternal
            LOGGER.error("Gagal inisialisasi scraping %s: %s", page, exc)
            rows.extend(_fallback_scrape(page, pages_per_page))
            continue

        retries = 0
        for post in posts_iter:
            try:
                serialized = _serialize_post(post, page, max_comments)
                rows.append(serialized)
                time.sleep(delay)
            except Exception as exc:  # pragma: no cover
                retries += 1
                LOGGER.warning("Gagal memproses post di %s: %s", page, exc)
                if retries > 3:
                    LOGGER.error("Terlalu banyak error pada halaman %s, lanjut ke halaman berikut", page)
                    break
                time.sleep(delay * 2)

    _dump_jsonl(out_path, rows)
    return rows


def _dump_jsonl(path: str, rows: List[Dict[str, object]]) -> None:
    from utils.io import append_jsonl  # late import untuk hindari circular

    append_jsonl(path, rows)
    LOGGER.info("Scraping selesai. Total dokumen: %d -> %s", len(rows), path)
