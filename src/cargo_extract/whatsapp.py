"""Membaca file ekspor chat WhatsApp (.txt) dan memotongnya per percakapan (episode).

Format yang sudah dicek dengan ekspor asli:
    [9/8/26, 10:35:22 AM] Nama: teks          (iPhone, bahasa Inggris)
Format Android juga dikenali, tapi belum dicek dengan ekspor asli:
    24/10/26 23.26 - Nama: teks
    10/24/26, 11:26 PM - Nama: teks
Baris tanpa tanggal di depannya adalah lanjutan pesan sebelumnya.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import NamedTuple

from .schemas import Lampiran, Pesan

_TGL = r"(?P<tgl>\d{1,2}/\d{1,2}/\d{2,4})"
_JAM = r"(?P<jam>\d{1,2}[.:]\d{2}(?:[.:]\d{2})?(?: ?[AP]M)?)"
POLA_PESAN = [
    re.compile(rf"^\[{_TGL},? {_JAM}\] (?P<nama>.+?): (?P<teks>.*)$"),   # iPhone
    re.compile(rf"^{_TGL},? {_JAM} - (?P<nama>.+?): (?P<teks>.*)$"),     # Android
]
POLA_AWALAN_TANGGAL = re.compile(rf"^\[?{_TGL},? {_JAM}\]?( -)? ")      # pesan sistem tanpa nama

POLA_MEDIA = re.compile(
    r"<(?:image|video|audio|sticker|GIF|document) omitted>"
    r"|<attached: (?P<file1>[^>]+)>"
    r"|(?P<file2>\S+\.\w{2,4}) \((?:file attached|file terlampir)\)"
    r"|<Media (?:omitted|tidak disertakan)>",
    re.IGNORECASE,
)
TEKS_SISTEM = ("end-to-end encrypted", "terenkripsi secara end-to-end", " is a contact.")
POLA_DIEDIT = re.compile(r"\s*<(?:This message was edited|Pesan ini diedit)>", re.IGNORECASE)
JEDA_EPISODE = timedelta(days=7)


class HasilBaca(NamedTuple):
    pesan: list[Pesan]
    nama_pelanggan: set[str]   # nama kontak WhatsApp, dipakai samarkan.py


def _cocokkan(baris: str) -> re.Match | None:
    for pola in POLA_PESAN:
        if m := pola.match(baris):
            return m
    return None


def _urutan_tanggal(cocok: list[re.Match]) -> str:
    """'MD' (bulan dulu) atau 'DM', dari angka > 12; jika ambigu, AM/PM berarti format AS."""
    for m in cocok:
        a, b, _ = m["tgl"].split("/")
        if int(a) > 12:
            return "DM"
        if int(b) > 12:
            return "MD"
    return "MD" if any(m["jam"].endswith("M") for m in cocok) else "DM"


def _waktu(m: re.Match, urutan: str) -> datetime:
    a, b, tahun = m["tgl"].split("/")
    bulan, hari = (a, b) if urutan == "MD" else (b, a)
    jam = re.match(r"(\d{1,2})[.:](\d{2})(?:[.:](\d{2}))?(?: ?([AP]M))?", m["jam"])
    h, menit, detik, ampm = int(jam[1]), int(jam[2]), int(jam[3] or 0), jam[4]
    if ampm:
        h = h % 12 + (12 if ampm == "PM" else 0)
    tahun = int(tahun) + 2000 if len(tahun) == 2 else int(tahun)
    return datetime(tahun, int(bulan), int(hari), h, menit, detik)


def _jenis_media(teks: str) -> str:
    t = teks.lower()
    if re.search(r"image|sticker|gif|photo|\.(jpe?g|png|webp)", t):
        return "foto"
    if ".pdf" in t:
        return "pdf"
    if re.search(r"\.xlsx?", t):
        return "excel"
    return "lainnya"


def baca_ekspor(path: Path, nama_admin: set[str] = frozenset({"You", "Anda"})) -> HasilBaca:
    teks = path.read_text(encoding="utf-8-sig")
    teks = teks.replace("‎", "").replace("‏", "").replace(" ", " ").replace(" ", " ")
    baris_cocok = [(baris, _cocokkan(baris)) for baris in teks.splitlines()]
    urutan = _urutan_tanggal([m for _, m in baris_cocok if m])

    mentah: list[dict] = []
    for baris, m in baris_cocok:
        if m:
            mentah.append({"nama": m["nama"].strip(), "waktu": _waktu(m, urutan), "baris": [m["teks"]]})
        elif POLA_AWALAN_TANGGAL.match(baris):
            continue                       # pesan sistem, mis. "... terenkripsi secara end-to-end"
        elif mentah:
            mentah[-1]["baris"].append(baris)
        # baris sebelum pesan pertama (pemberitahuan enkripsi iPhone) diabaikan

    pesan, nama_pelanggan = [], set()
    for p in mentah:
        isi = POLA_DIEDIT.sub("", "\n".join(p["baris"])).strip()
        if any(s in isi for s in TEKS_SISTEM):
            continue
        lampiran = []
        for media in POLA_MEDIA.finditer(isi):
            file = media["file1"] or media["file2"]
            lampiran.append(Lampiran(jenis=_jenis_media(media[0]), file=f"{path.parent.name}/{file}" if file else None))
        isi = POLA_MEDIA.sub(lambda media: f"[{_jenis_media(media[0])}]", isi)
        admin = p["nama"] in nama_admin
        if not admin:
            nama_pelanggan.add(p["nama"])
        pesan.append(Pesan(pengirim="admin" if admin else "pelanggan", teks=isi, lampiran=lampiran, waktu=p["waktu"]))
    return HasilBaca(pesan, nama_pelanggan)


def potong_episode(pesan: list[Pesan], jeda: timedelta = JEDA_EPISODE) -> list[list[Pesan]]:
    """Episode baru dimulai jika tidak ada pesan selama `jeda` (default 7 hari)."""
    episode: list[list[Pesan]] = []
    for p in pesan:
        sebelum = episode[-1][-1] if episode else None
        if sebelum is None or (p.waktu and sebelum.waktu and p.waktu - sebelum.waktu >= jeda):
            episode.append([p])
        else:
            episode[-1].append(p)
    return episode
