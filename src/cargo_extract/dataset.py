"""Membaca dataset chat berlabel (JSONL, satu ContohChat per baris)."""
from __future__ import annotations

from pathlib import Path

from .schemas import ContohChat, Pesan


def muat_chats(path: Path) -> list[ContohChat]:
    with path.open(encoding="utf-8") as f:
        return [ContohChat.model_validate_json(baris) for baris in f if baris.strip()]


def teks_chat(pesan: list[Pesan]) -> str:
    """Chat sebagai teks untuk prompt: satu pesan per baris, 'pengirim: teks'."""
    return "\n".join(f"{p.pengirim}: {p.teks}" for p in pesan)


def format_chat(contoh: ContohChat) -> str:
    return teks_chat(contoh.pesan)


def parse_teks_chat(teks: str) -> list[Pesan]:
    """Kebalikan teks_chat: baris 'pelanggan: ...' / 'admin: ...'; baris tanpa awalan adalah
    lanjutan pesan sebelumnya. Teks tanpa awalan sama sekali dianggap satu pesan pelanggan."""
    pesan: list[Pesan] = []
    for baris in teks.strip().splitlines():
        awalan, _, isi = baris.partition(":")
        if awalan.strip().lower() in ("pelanggan", "admin"):
            pesan.append(Pesan(pengirim=awalan.strip().lower(), teks=isi.strip()))
        elif pesan:
            pesan[-1] = pesan[-1].model_copy(update={"teks": pesan[-1].teks + "\n" + baris})
        else:
            pesan.append(Pesan(pengirim="pelanggan", teks=baris))
    return pesan
