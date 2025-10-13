"""Logger util sederhana.

Semua modul menggunakan konfigurasi logger ini agar konsisten.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional


def get_logger(name: str, log_dir: Optional[str] = None) -> logging.Logger:
    """Bangun logger dengan output ke console dan file (jika diminta)."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    target_dir = log_dir or os.getenv("LOG_DIR")
    if target_dir:
        Path(target_dir).mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(Path(target_dir) / "pipeline.log")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger
