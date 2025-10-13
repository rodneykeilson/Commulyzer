"""Konfigurasi pytest untuk memastikan modul lokal dapat diimpor."""
from __future__ import annotations

import sys
from pathlib import Path

# Pastikan direktori root proyek ada pada sys.path agar import relatif bekerja.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
