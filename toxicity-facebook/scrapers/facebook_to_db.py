"""Utilitas untuk scraping group Facebook langsung ke database.

Modul ini sengaja menjaga perilaku "aman secara default" sehingga scraping
jaringan hanya berjalan ketika pengguna benar-benar mengizinkan. Seluruh log
menggunakan Bahasa Indonesia untuk mempermudah debugging lokal.
"""
from __future__ import annotations

import os
import time
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Union

from sqlalchemy.engine import make_url  # type: ignore

from storage.repository import ToxicityRepository
from utils.io import read_jsonl
from utils.logger import get_logger

LOGGER = get_logger(__name__)

SAMPLE_FALLBACK_PATH = Path("data/sample/sample_group_post.jsonl")

try:  # pragma: no cover - path runtime
    from facebook_scraper import get_posts  # type: ignore
except ImportError:  # pragma: no cover - dependency opsional
    get_posts = None  # type: ignore


def _env_allows_scrape() -> bool:
    """Cek env flag global agar operator dapat mengaktifkan scraping via .env."""
    return os.getenv("ALLOW_SCRAPE", "false").strip().lower() in {"1", "true", "yes"}


def _ensure_sqlite_dir(db_url: str) -> Path:
    """Pastikan direktori SQLite tersedia sebelum koneksi dibuat."""
    try:
        url = make_url(db_url)
    except Exception:
        return Path(".")
    if url.drivername != "sqlite" or not url.database:
        return Path(".")
    db_path = Path(url.database)
    if not db_path.is_absolute():
        db_path = Path.cwd() / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def _coerce_time(value: object) -> Optional[str]:
    """Normalisasi berbagai representasi waktu menjadi ISO-8601."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _extract_reactions(post: Dict[str, object]) -> Dict[str, int]:
    """Ringkas struktur reaksi yang bervariasi dari facebook_scraper."""
    reactions = post.get("reactions") or post.get("reactions_full") or {}
    if isinstance(reactions, dict):
        return {str(key): int(value) for key, value in reactions.items()}
    if isinstance(reactions, list):
        result: Dict[str, int] = {}
        for item in reactions:
            label = str(item.get("type", "unknown"))
            result[label] = int(item.get("count", 0))
        return result
    return {}


def _normalise_comments(raw_comments: Iterable[Dict[str, object]], max_comments: int) -> List[Dict[str, object]]:
    """Ambil sebagian komentar untuk menghindari penyimpanan berlebih."""
    comments: List[Dict[str, object]] = []
    for comment in raw_comments:
        comment_id = comment.get("comment_id") or comment.get("comment_fbid")
        if not comment_id:
            continue
        comments.append(
            {
                "comment_id": str(comment_id),
                "text": comment.get("comment_text") or comment.get("text"),
                "time": _coerce_time(comment.get("comment_time") or comment.get("time")),
            }
        )
        if len(comments) >= max_comments:
            break
    return comments


def _is_public_group(post_payload: Dict[str, object]) -> bool:
    """Gunakan metadata privacy di post pertama sebagai indikator status group."""
    privacy = post_payload.get("privacy")
    if isinstance(privacy, str):
        return privacy.strip().lower() == "public"
    if isinstance(privacy, dict):
        description = str(privacy.get("description") or privacy.get("value") or "").lower()
        return "public" in description
    # Beberapa versi library tidak mengembalikan privacy; fallback ke True.
    return True


def _normalise_post(
    post_payload: Dict[str, object],
    group_identifier: str,
    max_comments: int,
) -> Dict[str, object]:
    """Normalisasi struktur post agar kompatibel dengan repository."""
    raw_comments = post_payload.get("comments_full")
    if not isinstance(raw_comments, list):
        raw_comments = []
    group_id = post_payload.get("group_id") or post_payload.get("group") or group_identifier
    group_name = post_payload.get("group_name") or post_payload.get("group") or group_identifier
    fetched_time = datetime.now(tz=timezone.utc).isoformat()
    return {
        "post_id": post_payload.get("post_id"),
        "page": group_identifier,
        "group_id": group_id,
        "group_name": group_name,
        "time": _coerce_time(post_payload.get("time")),
        "text": post_payload.get("text"),
        "comments_count": post_payload.get("comments") or len(raw_comments),
        "reactions_summary": _extract_reactions(post_payload),
        "fetched_time": fetched_time,
        "comments_sample": _normalise_comments(raw_comments, max_comments),
        "provenance": {
            "source": "facebook_group",
            "group_identifier": group_identifier,
            "group_id": group_id,
            "group_name": group_name,
            "fetched_time": fetched_time,
        },
    }


def _prepare_cookies_arg(cookies_path: Optional[str]) -> Optional[Union[str, Dict[str, str]]]:
    """Validasi argumen cookie dan dukung pembacaan dari environment."""
    if cookies_path:
        path = Path(cookies_path)
        if not path.exists():
            LOGGER.warning("File cookie %s tidak ditemukan. Lanjut tanpa autentikasi.", cookies_path)
            return None
        LOGGER.info("Menggunakan cookie dari file %s", path)
        return str(path)

    env_path = os.getenv("FACEBOOK_COOKIES_PATH") or os.getenv("FACEBOOK_COOKIES_FILE")
    if env_path:
        path = Path(env_path)
        if path.exists():
            LOGGER.info("Menggunakan cookie dari environment path %s", path)
            return str(path)
        LOGGER.warning("FACEBOOK_COOKIES_PATH mengarah ke berkas yang tidak ada: %s", env_path)

    env_cookie_json = os.getenv("FACEBOOK_COOKIES")
    if env_cookie_json:
        try:
            parsed = json.loads(env_cookie_json)
        except json.JSONDecodeError as exc:
            LOGGER.warning("Gagal mem-parsing FACEBOOK_COOKIES sebagai JSON: %s", exc)
            return None
        if isinstance(parsed, dict):
            LOGGER.info("Menggunakan cookie dari environment FACEBOOK_COOKIES.")
            return {str(k): str(v) for k, v in parsed.items()}
        LOGGER.warning("FACEBOOK_COOKIES harus berupa JSON object dengan pasangan kunci-nilai.")

    return None


def scrape_group_to_db(
    group_identifier: str,
    db_url: str = "sqlite:///data/toxicity.db",
    max_posts: int = 100,
    comments_per_post: int = 10,
    delay: float = 1.5,
    cookies_path: Optional[str] = None,
    allow_scrape: bool = False,
) -> dict:
    """Scrape posts+comments dari Facebook group dan simpan ke DB.

    Safety: hanya berjalan jika allow_scrape=True atau env ALLOW_SCRAPE=true.
    Mengecek apakah group publik sebelum scraping; jika tidak publik, fungsi akan
    kembali tanpa menyimpan data apapun.
    """
    if not allow_scrape and not _env_allows_scrape():
        LOGGER.info("Scraping dibatalkan: aktifkan --allow-scrape atau ALLOW_SCRAPE=true.")
        return {
            "status": "skipped",
            "group": group_identifier,
            "message": "Scraping dinonaktifkan secara default.",
        }

    if max_posts <= 0:
        return {
            "status": "skipped",
            "group": group_identifier,
            "message": "Parameter max_posts harus lebih dari nol.",
        }

    if get_posts is None:
        LOGGER.error("facebook_scraper belum terinstal. Jalankan `pip install facebook-scraper`.")
        return {
            "status": "error",
            "group": group_identifier,
            "message": "facebook_scraper tidak tersedia.",
        }

    _ensure_sqlite_dir(db_url)
    repo = ToxicityRepository(db_url)

    cookies_arg = _prepare_cookies_arg(cookies_path)
    pages_to_request = max(1, (max_posts + 9) // 10)
    options = {
        "comments": comments_per_post,
        "reactions": True,
        "allow_extra_meta": True,
        "posts_per_page": min(max_posts, 25),
    }

    collected: List[Dict[str, object]] = []
    fetch_kwargs = {
        "group": group_identifier,
        "options": options,
        "cookies": cookies_arg,
    }
    use_page_limit = True

    while True:
        try:
            if use_page_limit:
                posts_iter = get_posts(  # type: ignore[misc]
                    pages=pages_to_request,
                    page_limit=max_posts,
                    **fetch_kwargs,
                )
            else:
                posts_iter = get_posts(  # type: ignore[misc]
                    pages=pages_to_request,
                    **fetch_kwargs,
                )

            for index, post_payload in enumerate(posts_iter):
                if index == 0 and not _is_public_group(post_payload):
                    LOGGER.warning("Group %s terdeteksi tidak publik. Scraping dihentikan.", group_identifier)
                    return {
                        "status": "blocked",
                        "group": group_identifier,
                        "message": "Group tidak publik atau membutuhkan login.",
                    }
                collected.append(post_payload)
                if len(collected) >= max_posts:
                    break
                time.sleep(max(delay, 0))
            break
        except TypeError as exc:
            if use_page_limit and "page_limit" in str(exc):
                LOGGER.info(
                    "page_limit tidak didukung oleh facebook_scraper versi ini: %s. Mengulang tanpa page_limit.",
                    exc,
                )
                use_page_limit = False
                continue
            raise
        except Exception as exc:  # pragma: no cover - library eksternal
            LOGGER.error("Gagal memulai scraping group %s: %s", group_identifier, exc)
            return {
                "status": "error",
                "group": group_identifier,
                "message": f"Gagal inisialisasi scraping: {exc}",
            }

    if not collected:
        LOGGER.info("Tidak ada post baru dari group %s.", group_identifier)
        return {
            "status": "empty",
            "group": group_identifier,
            "posts_saved": 0,
        }

    seen: set[str] = set()
    normalised: List[Dict[str, object]] = []
    for post_payload in collected:
        normalised_post = _normalise_post(post_payload, group_identifier, comments_per_post)
        post_id = normalised_post.get("post_id")
        if not post_id:
            continue
        if post_id in seen:
            continue
        seen.add(str(post_id))
        normalised.append(normalised_post)

    if not normalised:
        return {
            "status": "empty",
            "group": group_identifier,
            "posts_saved": 0,
        }

    saved = repo.save_posts(group_identifier, normalised, max_comments=comments_per_post)
    return {
        "status": "success",
        "group": group_identifier,
        "posts_saved": int(saved),
        "attempted": len(normalised),
        "source": "network",
    }


def load_sample_group_posts(group_identifier: str) -> List[Dict[str, object]]:
    """Baca sample JSONL untuk keperluan pengembangan tanpa jaringan."""
    rows = read_jsonl(SAMPLE_FALLBACK_PATH)
    if not rows:
        raise FileNotFoundError(
            f"Sample group JSONL tidak ditemukan di {SAMPLE_FALLBACK_PATH}."
        )
    patched: List[Dict[str, object]] = []
    for row in rows:
        patched_row = dict(row)
        patched_row["page"] = group_identifier
        patched_row.setdefault("group_name", group_identifier)
        patched_row.setdefault("group_id", group_identifier)
        patched.append(patched_row)
    return patched
