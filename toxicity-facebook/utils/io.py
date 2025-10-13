"""Utilitas I/O untuk JSONL dan deduplikasi."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Iterable, List, Dict, Any

from utils.logger import get_logger

LOGGER = get_logger(__name__)


def ensure_parent(path: Path) -> None:
    """Pastikan direktori induk ada."""
    path.parent.mkdir(parents=True, exist_ok=True)


def write_jsonl(path: str | Path, rows: Iterable[Dict[str, Any]]) -> None:
    """Simpan iterable dict ke file JSONL."""
    target = Path(path)
    ensure_parent(target)
    with target.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    LOGGER.info("Tersimpan %s", target)


def append_jsonl(path: str | Path, rows: Iterable[Dict[str, Any]]) -> None:
    """Append data ke JSONL."""
    target = Path(path)
    ensure_parent(target)
    with target.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: str | Path) -> List[Dict[str, Any]]:
    """Baca JSONL dan kembalikan list dict."""
    data: List[Dict[str, Any]] = []
    target = Path(path)
    if not target.exists():
        LOGGER.warning("File %s tidak ditemukan", target)
        return data
    with target.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data.append(json.loads(line))
    return data


def rotate_file(path: str | Path, keep: int = 3) -> None:
    """Rotasi file lama, simpan maksimum `keep` versi."""
    target = Path(path)
    if not target.exists():
        return
    for idx in range(keep, 0, -1):
        older = target.with_suffix(target.suffix + f".{idx}")
        newer = target.with_suffix(target.suffix + f".{idx-1}") if idx > 1 else target
        if newer.exists():
            if idx == keep:
                older.unlink(missing_ok=True)
            newer.rename(target.with_suffix(target.suffix + f".{idx}"))


def deduplicate_jsonl(path: str | Path, key: str = "post_id") -> int:
    """Dedup berdasarkan key, mengembalikan jumlah baris terhapus."""
    target = Path(path)
    if not target.exists():
        return 0
    seen = set()
    kept: List[Dict[str, Any]] = []
    removed = 0
    for row in read_jsonl(target):
        value = row.get(key)
        if value in seen:
            removed += 1
            continue
        seen.add(value)
        kept.append(row)
    write_jsonl(target, kept)
    return removed


def backup_file(path: str | Path, backup_dir: str | Path) -> Path:
    """Simpan salinan file ke backup_dir."""
    target = Path(path)
    dest_dir = Path(backup_dir)
    if not target.exists():
        raise FileNotFoundError(f"File {target} tidak ditemukan")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / target.name
    shutil.copy2(target, dest)
    LOGGER.info("Backup %s -> %s", target, dest)
    return dest
