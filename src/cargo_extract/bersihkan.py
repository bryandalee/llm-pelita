"""Membuang pesan template admin (quick reply WhatsApp Business) sebelum chat dikirim ke model.

Template dikenali dari frasa penanda di data/referensi/template_admin.txt. Pricelist umum
dikenali dari harganya (lihat tanda.jawaban_harga_khusus). Pesan pelanggan tidak pernah dibuang.
"""
from __future__ import annotations

from functools import lru_cache

from . import config
from .schemas import Pesan
from .tanda import POLA_HARGA, jawaban_harga_khusus


@lru_cache
def frasa_template() -> tuple[str, ...]:
    baris = (config.DATA_DIR / "referensi" / "template_admin.txt").read_text(encoding="utf-8").splitlines()
    return tuple(b.strip().casefold() for b in baris if b.strip() and not b.startswith("#"))


def template_admin(p: Pesan) -> bool:
    if p.pengirim != "admin":
        return False
    teks = p.teks.casefold()
    if any(frasa in teks for frasa in frasa_template()):
        return True
    return bool(POLA_HARGA.search(p.teks)) and not jawaban_harga_khusus(p.teks)


def buang_template(pesan: list[Pesan]) -> list[Pesan]:
    return [p for p in pesan if not template_admin(p)]
