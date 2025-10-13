"""Discovery halaman Facebook berdasarkan kata kunci."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional

import requests  # type: ignore

from utils.logger import get_logger

LOGGER = get_logger(__name__)
GOOGLE_API_ENDPOINT = "https://www.googleapis.com/customsearch/v1"


def _parse_facebook_usernames(items: List[dict]) -> List[str]:
    """Ambil kandidat username/page dari hasil Google."""
    pages: List[str] = []
    for item in items:
        link = item.get("link", "")
        if "facebook.com" not in link:
            continue
        parts = link.split("facebook.com/")
        if len(parts) < 2:
            continue
        slug = parts[1].split("?")[0].split("/")[0].strip()
        if not slug:
            continue
        slug = slug.replace("pages/", "").strip("/")
        if slug and slug not in pages:
            pages.append(slug)
    return pages


def discover_pages_from_keyword(
    keyword: str,
    max_candidates: int = 20,
    google_api_key: Optional[str] = None,
) -> List[str]:
    """Discover halaman Facebook dengan kombinasi kata kunci.

    Jika Google API Key tidak tersedia, pengguna diminta
    menyediakan file `pages.txt` secara manual (lihat README).
    """
    key = google_api_key or os.getenv("GOOGLE_API_KEY")
    cx = os.getenv("GOOGLE_CSE_ID")

    if key and cx:
        params = {
            "key": key,
            "cx": cx,
            "q": f"site:facebook.com {keyword} pages",
            "num": min(max_candidates, 10),
        }
        try:
            response = requests.get(GOOGLE_API_ENDPOINT, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            items = data.get("items", [])
            pages = _parse_facebook_usernames(items)
            LOGGER.info("Ditemukan %d kandidat halaman via Google CSE", len(pages))
            return pages[:max_candidates]
        except requests.RequestException as exc:
            LOGGER.warning("Gagal pakai Google CSE: %s", exc)

    LOGGER.info(
        "Tidak menggunakan Google CSE. Silakan sediakan file pages.txt berisi satu nama halaman per baris."
    )
    manual_file = Path("pages.txt")
    if manual_file.exists():
        try:
            pages = [line.strip() for line in manual_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            return pages[:max_candidates]
        except OSError as exc:
            LOGGER.error("Gagal membaca pages.txt: %s", exc)
            return []
    LOGGER.warning("pages.txt tidak ditemukan. Kembalikan list kosong.")
    return []
