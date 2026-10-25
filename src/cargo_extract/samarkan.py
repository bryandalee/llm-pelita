"""Menyamarkan chat asli sebelum dipakai di luar data/raw/.

Yang diganti:
- nomor HP (juga tanpa kode negara), deret angka panjang (mis. nomor rekening), email, ID WeChat,
  dan marga di sapaan Mandarin (苏先生 -> 某先生);
- nama dari kolom formulir ("Nama saya:", "Nama Lengkap :"), nama kontak WhatsApp, dan nama
  tambahan yang diberikan;
- marking code (diturunkan dari nama kontak, mis. "AB-CD/ BY SEA" -> AB/CD, AB-CD, ...);
- baris alamat jalan/desa/kelurahan, kode pos di blok alamat, dan nomor dokumen (No.PL, Nota, Resi).
Angka barang (koli, berat, ukuran) dan nama kota TIDAK diubah, supaya label tetap berlaku.

Ini berbasis aturan dan tidak sempurna: selalu baca file pratinjau sebelum hasilnya dipakai.
"""
from __future__ import annotations

import re

from .schemas import Pesan

POLA_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
POLA_HP = re.compile(
    r"\(?\+\d{1,3}\)?[\s-]?\d{2,4}[\s-]?\d{3,4}[\s-]?\d{3,5}"
    r"|\b0\d{2,3}[\s-]?\d{3,4}[\s-]?\d{3,5}\b"
)
# Deret >= 10 angka tanpa pemisah: HP China tanpa +86, nomor rekening, dsb.
# (harga dan ukuran selalu memakai pemisah seperti titik atau x).
POLA_NOMOR_PANJANG = re.compile(r"\b\d{10,}\b")
POLA_WECHAT = re.compile(r"(?P<label>(?:微信|wechat)\s*[:：]\s*)(?P<nilai>[\w.\-]+)", re.IGNORECASE)
POLA_MARGA_ZH = re.compile(r"[一-鿿](?=先生|小姐|女士)")   # 苏先生 -> 某先生
# [ \t] (bukan \s) supaya kolom formulir yang kosong tidak "mengambil" baris berikutnya.
POLA_NAMA_FORM = re.compile(r"^[ \t]*Nama(?: Lengkap| saya)?[ \t]*:[ \t]*(?P<nilai>\S.*)$", re.IGNORECASE | re.MULTILINE)
POLA_DOKUMEN = re.compile(
    r"^(?P<label>[ \t]*(?:No\.?[ \t]*PL|Nota[^:\n]*|No\.?[ \t]*Resi|Resi)[ \t]*:[ \t]*)(?P<nilai>\S+)",
    re.IGNORECASE | re.MULTILINE,
)
POLA_LABEL_ALAMAT = re.compile(r"^\s*Alamat[^:\n]*:", re.IGNORECASE)
POLA_LABEL = re.compile(r"^\s*[A-Za-z][\w. /+]{1,30}:")
# Baris alamat di bawah tingkat kecamatan. Kecamatan dan kota sengaja dipertahankan (dipakai untuk kota_tujuan).
# Di luar blok alamat, "jalan" baru dianggap alamat jika diikuti nama ("Jalan Sudirman"), "raya",
# atau kata kapital + nomor ("JALAN MELATI 5"), karena "bisa jalan (BY AIR)" berarti "bisa dikirim".
POLA_JALAN = re.compile(
    r"\b(?:jl|jln|gg|gang|blok|komplek|perum(?:ahan)?|apartemen|rt|rw|desa|dusun|kelurahan)\b"
    r"|\bjalan\s+(?:raya\b|(?-i:[A-Z][a-z])|(?-i:[A-Z]+\s+\d))",
    re.IGNORECASE,
)
# Di dalam blok alamat (setelah "Alamat ...:") cukup ada kata jalan atau nomor rumah.
POLA_JALAN_BLOK = re.compile(POLA_JALAN.pattern + r"|\bjalan\b|\bno\.?\s*\d", re.IGNORECASE)
POLA_KODEPOS = re.compile(r"\b\d{5}\b")
KATA_BUKAN_MARKING = {"BY", "SEA", "AIR", "LAUT", "UDARA", "VIA"}


class Penyamar:
    def __init__(self, nama_kontak: set[str], nama_tambahan: list[str] = ()):
        self.pengganti: dict[str, str] = {}   # asli -> palsu, untuk diperiksa manual
        self.nama = {n for n in nama_tambahan if n.strip()}
        self.pola_marking: list[tuple[str, re.Pattern]] = []
        for kontak in nama_kontak:
            token = [t for t in re.findall(r"[A-Za-z0-9]+", kontak) if t.upper() not in KATA_BUKAN_MARKING]
            if len(token) >= 2 and any(t.isalpha() for t in token):
                pola = re.compile(r"\b" + r"[\W_]{0,3}".join(map(re.escape, token)) + r"\b", re.I)
                self.pola_marking.append((kontak, pola))
            self.nama |= {t for t in token if t.isalpha() and len(t) >= 3}

    def _palsu(self, asli: str, jenis: str) -> str:
        kunci = asli.strip().casefold()
        if kunci not in self.pengganti:
            n = sum(v.startswith(f"[{jenis}") for v in self.pengganti.values()) + 1
            self.pengganti[kunci] = f"[{jenis}{n}]"
        return self.pengganti[kunci]

    def kenali_nama(self, teks: str) -> None:
        for m in POLA_NAMA_FORM.finditer(teks):
            nilai = m["nilai"].strip()
            self.nama.add(nilai)
            self.nama |= {k for k in re.findall(r"[^\W\d_]+", nilai) if len(k) >= 3}

    def _alamat(self, teks: str) -> str:
        hasil, di_blok = [], False
        for baris in teks.split("\n"):
            if POLA_LABEL_ALAMAT.match(baris):
                di_blok = True
                label, _, nilai = baris.partition(":")
                hasil.append(f"{label}:{self._baris_alamat(nilai)}" if nilai.strip() else baris)
                continue
            if di_blok and (not baris.strip() or POLA_LABEL.match(baris)):
                di_blok = False
            if di_blok:
                hasil.append(self._baris_alamat(baris))
            else:
                hasil.append("[ALAMAT JALAN]" if POLA_JALAN.search(baris) else baris)
        return "\n".join(hasil)

    @staticmethod
    def _baris_alamat(baris: str) -> str:
        return "[ALAMAT JALAN]" if POLA_JALAN_BLOK.search(baris) else POLA_KODEPOS.sub("[KODEPOS]", baris)

    def samarkan(self, teks: str) -> str:
        teks = POLA_EMAIL.sub(lambda m: self._palsu(m[0], "EMAIL"), teks)
        teks = POLA_HP.sub(lambda m: self._palsu(m[0], "HP"), teks)
        teks = POLA_NOMOR_PANJANG.sub(lambda m: self._palsu(m[0], "NOMOR"), teks)
        teks = POLA_WECHAT.sub(lambda m: m["label"] + self._palsu(m["nilai"], "WECHAT"), teks)
        teks = POLA_MARGA_ZH.sub("某", teks)
        teks = POLA_DOKUMEN.sub(lambda m: m["label"] + self._palsu(m["nilai"], "DOK"), teks)
        teks = self._alamat(teks)
        for kontak, pola in self.pola_marking:
            teks = pola.sub(lambda m: self._palsu(kontak, "MARKING"), teks)
        if self.nama:
            pola_nama = re.compile(
                r"\b(?:" + "|".join(map(re.escape, sorted(self.nama, key=len, reverse=True))) + r")\b", re.I)
            teks = pola_nama.sub(lambda m: self._palsu(m[0], "NAMA"), teks)
        return teks


def samarkan_pesan(
    pesan: list[Pesan], nama_kontak: set[str], nama_tambahan: list[str] = ()
) -> tuple[list[Pesan], dict[str, str]]:
    """Samarkan semua pesan satu ekspor dengan pengganti yang konsisten. Kembalikan juga petanya."""
    penyamar = Penyamar(nama_kontak, nama_tambahan)
    for p in pesan:
        penyamar.kenali_nama(p.teks)
    hasil = [p.model_copy(update={"teks": penyamar.samarkan(p.teks)}) for p in pesan]
    return hasil, penyamar.pengganti
