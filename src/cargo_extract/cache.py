"""Cache respons model di .cache/, supaya tiap chat cukup diproses sekali per (prompt, model).

Kunci = hash dari (versi prompt, isi prompt, model, teks chat), jadi mengubah isi prompt
otomatis membuat cache baru.
"""
from __future__ import annotations

import hashlib

from .config import CACHE_DIR


def kunci(*bagian: str) -> str:
    return hashlib.sha256("\x1f".join(bagian).encode("utf-8")).hexdigest()


def ambil(k: str) -> str | None:
    path = CACHE_DIR / f"{k}.json"
    return path.read_text(encoding="utf-8") if path.exists() else None


def simpan(k: str, isi: str) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{k}.json").write_text(isi, encoding="utf-8")
