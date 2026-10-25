"""Tanda per episode chat asli: jenis episode dan titik potong input.

Disimpan terpisah dari draft (data/privat/tanda.json), supaya impor ulang sebuah ekspor tidak
menghapus tanda yang sudah dibuat. Aturannya: docs/panduan_label.md, bagian "Chat asli".
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import config
from .schemas import DraftChat, Pesan, TandaEpisode

# Harga apa pun: "7 jt", "230rb", "Rp 89.000", "1.260.000".
POLA_HARGA = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:jt|juta|rb|ribu)\b|\bRp\.?\s?\d|\b\d{1,3}(?:\.\d{3}){2,}\b", re.IGNORECASE)
POLA_TARIF_LAUT = re.compile(r"\d+(?:[.,]\d+)?\s*(?:jt|juta)\s*/\s*cbm", re.IGNORECASE)    # "7 jt / cbm"
POLA_TARIF_UDARA = re.compile(r"\d+(?:[.,]\d+)?\s*(?:rb|ribu)\s*/\s*kg", re.IGNORECASE)    # "230rb/kg"
# Hitungan untuk kiriman ini: "65x45x50=146.250", "0.15 cbm x 7.000.000 = ..."
POLA_HITUNG = re.compile(r"\d\s*[x×*]\s*\d[^\n]*=")


def file_tanda() -> Path:
    return config.PRIVAT_DIR / "tanda.json"


def jawaban_harga_khusus(teks: str) -> bool:
    """Harga yang sudah disesuaikan untuk barang pelanggan, bukan pricelist umum.

    Khusus: ada hitungan, tepat satu tarif laut (kategori sudah dipilih admin), tepat satu
    tarif udara, atau nominal total ("1.030.000", "89 rb"). Umum: daftar beberapa tarif laut,
    atau pasangan tarif udara branded/non-branded saja.
    """
    laut = len(POLA_TARIF_LAUT.findall(teks))
    udara = len(POLA_TARIF_UDARA.findall(teks))
    nominal = len(POLA_HARGA.findall(teks)) - laut - udara
    return bool(POLA_HITUNG.search(teks)) or laut == 1 or udara == 1 or nominal > 0


def saran_titik_potong(pesan: list[Pesan]) -> int | None:
    """Indeks pesan admin pertama yang menjawab harga khusus untuk kiriman ini."""
    for i, p in enumerate(pesan):
        if p.pengirim == "admin" and jawaban_harga_khusus(p.teks):
            return i
    return None


def muat_tanda(path: Path | None = None) -> dict[str, TandaEpisode]:
    path = path or file_tanda()
    if not path.exists():
        return {}
    return {k: TandaEpisode.model_validate(v) for k, v in json.loads(path.read_text(encoding="utf-8")).items()}


def simpan_tanda(id_episode: str, tanda: TandaEpisode, path: Path | None = None) -> None:
    path = path or file_tanda()
    semua = muat_tanda(path) | {id_episode: tanda}
    path.parent.mkdir(parents=True, exist_ok=True)
    isi = {k: v.model_dump() for k, v in sorted(semua.items())}
    path.write_text(json.dumps(isi, ensure_ascii=False, indent=2), encoding="utf-8")


def input_episode(draft: DraftChat, tanda: TandaEpisode | None) -> list[Pesan]:
    """Pesan yang masuk ke model: semua pesan sebelum titik potong."""
    if tanda is None or tanda.potong_sebelum is None:
        return draft.pesan
    return draft.pesan[: tanda.potong_sebelum]


def muat_draft(path: Path) -> list[DraftChat]:
    return [DraftChat.model_validate_json(b) for b in path.read_text(encoding="utf-8").splitlines() if b.strip()]
