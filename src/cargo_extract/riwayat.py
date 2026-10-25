"""Riwayat keputusan admin sebagai contoh di prompt (retrieval, tanpa training).

Bank contoh = episode asli berlabel. Untuk setiap chat dicari k contoh yang teks pelanggannya
paling mirip (embedding lokal lewat Ollama). Keputusan admin di contoh-contoh itu (jenis barang ->
kategori, branded) lalu ditambahkan ke prompt. Makin banyak chat dilabel, makin banyak contohnya.
Saat evaluasi, contoh dari ekspor (pelanggan) yang sama tidak dipakai, supaya tidak menyontek.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import ollama

from . import config
from .bersihkan import buang_template
from .schemas import ContohChat, Pesan

MODEL_EMBEDDING = "qwen3-embedding:0.6b"
K = 5

FungsiEmbed = Callable[[list[str]], list[list[float]]]


@dataclass
class Contoh:
    id: str
    sumber: str               # folder ekspor, mis. "ekspor_13"
    jenis_barang: str
    kategori: str | None
    branded: bool | None
    vektor: list[float]


def teks_pelanggan(pesan: list[Pesan]) -> str:
    return "\n".join(p.teks for p in buang_template(pesan) if p.pengirim == "pelanggan")[:1500]


def embed(teks: list[str]) -> list[list[float]]:
    return ollama.Client(host=config.OLLAMA_HOST).embed(model=MODEL_EMBEDDING, input=teks).embeddings


def sumber(id_episode: str) -> str:
    return id_episode.rsplit("_ep", 1)[0]


def bangun_bank(chats: list[ContohChat], fungsi_embed: FungsiEmbed = embed) -> list[Contoh]:
    """Hanya episode dengan jenis barang dan keputusan admin (kategori atau branded) yang berguna."""
    dipakai = [c for c in chats
               if c.label.jenis_barang and (c.label.kategori_barang or c.label.branded is not None)]
    if not dipakai:
        return []
    vektor = fungsi_embed([teks_pelanggan(c.pesan) for c in dipakai])
    return [
        Contoh(id=c.id, sumber=sumber(c.id), jenis_barang=c.label.jenis_barang,
               kategori=c.label.kategori_barang.value if c.label.kategori_barang else None,
               branded=c.label.branded, vektor=v)
        for c, v in zip(dipakai, vektor)
    ]


def _kosinus(a: list[float], b: list[float]) -> float:
    titik = sum(x * y for x, y in zip(a, b))
    return titik / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)) or 1.0)


def cari(bank: list[Contoh], vektor: list[float], kecuali_sumber: str | None = None, k: int = K) -> list[Contoh]:
    """k contoh paling mirip; k=0 berarti semua contoh, tetap diurutkan dari yang paling mirip."""
    kandidat = [c for c in bank if c.sumber != kecuali_sumber]
    urut = sorted(kandidat, key=lambda c: _kosinus(vektor, c.vektor), reverse=True)
    return urut[:k] if k > 0 else urut


def format_konteks(contoh: list[Contoh]) -> str:
    if not contoh:
        return ""
    baris = ["Contoh keputusan admin Pelita untuk barang yang mirip. Pakai sebagai acuan kategori_barang "
             "dan branded saja; kolom lain tetap dibaca dari chat:"]
    for c in contoh:
        udara = {True: "branded", False: "non-branded", None: "belum diputuskan"}[c.branded]
        baris.append(f"- {c.jenis_barang}: kategori {c.kategori or 'belum diputuskan'}, udara {udara}")
    return "\n".join(baris)


def konteks_untuk(pesan: list[Pesan], bank: list[Contoh], kecuali_sumber: str | None = None,
                  fungsi_embed: FungsiEmbed = embed, k: int = K) -> str:
    return format_konteks(cari(bank, fungsi_embed([teks_pelanggan(pesan)])[0], kecuali_sumber, k))
