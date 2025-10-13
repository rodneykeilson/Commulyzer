"""Utility untuk memastikan semua paket memiliki __init__.py.

Contoh: `python scripts/setup_dev.py`
"""
from __future__ import annotations

from pathlib import Path

from utils.logger import get_logger

LOGGER = get_logger(__name__)


def ensure_init_files(package_dirs: list[str]) -> None:
    for pkg in package_dirs:
        pkg_path = Path(pkg)
        if not pkg_path.exists():
            LOGGER.warning("Direktori %s tidak ditemukan", pkg)
            continue
        init_file = pkg_path / "__init__.py"
        if not init_file.exists():
            init_file.touch()
            LOGGER.info("Membuat __init__.py pada %s", pkg_path)
        else:
            LOGGER.info("__init__.py sudah ada di %s", pkg_path)


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    package_dirs = [
        project_root / "scrapers",
        project_root / "preprocess",
        project_root / "labeling",
        project_root / "train",
        project_root / "eval",
        project_root / "api",
        project_root / "utils",
    ]
    ensure_init_files([str(path) for path in package_dirs])


if __name__ == "__main__":
    main()
