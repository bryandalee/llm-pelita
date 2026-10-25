"""Akurasi per kolom: label vs prediksi (keduanya LabelPesanan).

Aturan cocok:
- jumlah_koli, kategori_barang, branded, jalur: sama persis
- berat_kg: selisih <= 1%; cbm: selisih <= 2%
- grup_koli: jumlah sama dan ketiga sisi cocok +-1 cm setelah sisi diurutkan
- kota_tujuan: sama (tanpa beda huruf besar/kecil); jenis_barang: cocok longgar, tetap dicek manual
- info_kurang: set persis sama, plus precision/recall per item di ringkasan

Setiap kolom dipisah menjadi benar / halusinasi (label null, prediksi isi) /
terlewat (label isi, prediksi null) / salah (dua-duanya isi, nilainya beda) /
diabaikan (labelnya belum pasti, lihat TAG_ABAIKAN; tidak ikut dihitung di akurasi).
"""
from __future__ import annotations

from collections import Counter

from cargo_extract.schemas import ContohChat, GrupKoli, LabelPesanan

KOLOM = [
    "jenis_barang", "kategori_barang", "branded", "jumlah_koli", "berat_kg",
    "grup_koli", "cbm", "kota_tujuan", "jalur", "info_kurang",
]
STATUS = ("benar", "salah", "halusinasi", "terlewat", "diabaikan")

# Tag di meta.tag yang membuat satu kolom tidak dinilai untuk chat itu.
TAG_ABAIKAN = {"kategori_perlu_dicek": "kategori_barang"}


def kolom_diabaikan(contoh: ContohChat) -> frozenset[str]:
    kolom = {TAG_ABAIKAN[t] for t in contoh.meta.tag if t in TAG_ABAIKAN}
    # Kategori dan branded adalah keputusan tarif admin berdasarkan barangnya; jika barang tidak
    # disebut di teks (mis. hanya di foto), model teks tidak mungkin menebaknya, jadi tidak dinilai
    # walaupun labelnya diisi.
    if contoh.label.jenis_barang is None:
        kolom |= {"kategori_barang", "branded"}
    return frozenset(kolom)


def akurasi(status: list[str]) -> float | None:
    dinilai = [s for s in status if s != "diabaikan"]
    return round(dinilai.count("benar") / len(dinilai), 3) if dinilai else None


def _kunci_grup(g: GrupKoli) -> tuple:
    return g.jumlah_koli or 0, tuple(sorted(g.dimensi_cm)) if g.dimensi_cm else ()


def _grup_cocok(label: list[GrupKoli], prediksi: list[GrupKoli]) -> bool:
    if len(label) != len(prediksi):
        return False
    for a, b in zip(sorted(label, key=_kunci_grup), sorted(prediksi, key=_kunci_grup)):
        if a.jumlah_koli != b.jumlah_koli or (a.dimensi_cm is None) != (b.dimensi_cm is None):
            return False
        if a.dimensi_cm and any(abs(x - y) > 1 for x, y in zip(sorted(a.dimensi_cm), sorted(b.dimensi_cm))):
            return False
    return True


def _cocok(kolom: str, a, b) -> bool:
    match kolom:
        case "berat_kg":
            return abs(a - b) <= 0.01 * a
        case "cbm":
            return abs(a - b) <= 0.02 * a
        case "jenis_barang":
            a, b = a.casefold().strip(), b.casefold().strip()
            return a in b or b in a
        case "kota_tujuan":
            return a.casefold() == b.casefold()
        case "grup_koli":
            return _grup_cocok(a, b)
        case _:
            return a == b


def bandingkan_kolom(
    label: LabelPesanan, prediksi: LabelPesanan, abaikan: frozenset[str] = frozenset()
) -> dict[str, str]:
    """{kolom: 'benar' | 'salah' | 'halusinasi' | 'terlewat' | 'diabaikan'}"""
    hasil = {}
    for kolom in KOLOM:
        a, b = getattr(label, kolom), getattr(prediksi, kolom)
        if kolom in abaikan:
            hasil[kolom] = "diabaikan"
        elif kolom == "info_kurang":
            hasil[kolom] = "benar" if set(a) == set(b) else "salah"
        elif a in (None, []):
            hasil[kolom] = "benar" if b in (None, []) else "halusinasi"
        elif b in (None, []):
            hasil[kolom] = "terlewat"
        else:
            hasil[kolom] = "benar" if _cocok(kolom, a, b) else "salah"
    return hasil


def ringkas(
    pasangan: list[tuple[LabelPesanan, LabelPesanan]], abaikan: list[frozenset[str]] | None = None
) -> dict:
    """Ringkasan untuk metrics.json dari daftar (label, prediksi)."""
    n = len(pasangan)
    abaikan = abaikan or [frozenset()] * n
    semua = [bandingkan_kolom(a, b, x) for (a, b), x in zip(pasangan, abaikan)]
    per_kolom = {}
    for kolom in KOLOM:
        status = [s[kolom] for s in semua]
        hitung = Counter(status)
        per_kolom[kolom] = {"akurasi": akurasi(status), **{s: hitung[s] for s in STATUS}}
    tp = sum(len(set(a.info_kurang) & set(b.info_kurang)) for a, b in pasangan)
    fp = sum(len(set(b.info_kurang) - set(a.info_kurang)) for a, b in pasangan)
    fn = sum(len(set(a.info_kurang) - set(b.info_kurang)) for a, b in pasangan)
    return {
        "jumlah_chat": n,
        "chat_semua_benar": sum(all(v in ("benar", "diabaikan") for v in s.values()) for s in semua),
        "per_kolom": per_kolom,
        "info_kurang": {
            "precision": round(tp / (tp + fp), 3) if tp + fp else None,
            "recall": round(tp / (tp + fn), 3) if tp + fn else None,
        },
    }
