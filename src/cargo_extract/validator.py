"""EkstraksiLLM -> Pesanan. Semua hitungan dan aturan ada di sini, tanpa LLM.

Langkah:
1. Konversi satuan (satuan.py). Satuan kosong: dimensi dianggap cm, berat dianggap kg,
   lalu beri peringatan SATUAN_DIASUMSIKAN.
2. jumlah_koli = jumlah semua grup; berat_kg = berat_total, atau per koli x jumlah.
   Jika keduanya ada dan berbeda -> BERAT_TIDAK_KONSISTEN.
3. CBM dari dimensi; jika tidak ada dimensi, pakai cbm_disebut. Beda > 10% -> CBM_TIDAK_COCOK.
4. Cek wajar: sisi, berat per koli, densitas kg/m3 (ambang di bawah, dituning di dev).
5. Minimum: laut < 0,1 CBM atau udara < 3 kg -> DI_BAWAH_MINIMUM.
6. Normalisasi kota lewat data/referensi/kota.csv; tidak ketemu -> KOTA_TIDAK_DIKENAL.
7. info_kurang sesuai docs/panduan_label.md.
"""
from __future__ import annotations

import csv
import re
from functools import lru_cache

from . import config
from .satuan import cbm as hitung_cbm
from .satuan import ke_cm, ke_kg
from .schemas import (
    BeratMentah,
    DimensiMentah,
    EkstraksiLLM,
    GrupKoli,
    InfoKurang,
    Jalur,
    KategoriBarang,
    KodePeringatan,
    Peringatan,
    Pesanan,
    SatuanBerat,
    SatuanPanjang,
)

# Ambang awal; dituning di dev set.
SISI_MIN_CM, SISI_MAKS_CM = 1, 300
BERAT_MAKS_PER_KOLI_KG = 200
DENSITAS_MIN, DENSITAS_MAKS = 15, 1500   # kg/m3
TOLERANSI_BERAT = 0.02
TOLERANSI_CBM = 0.10
MIN_CBM_LAUT = 0.1
MIN_KG_UDARA = 3


@lru_cache
def alias_kota() -> dict[str, str]:
    with (config.DATA_DIR / "referensi" / "kota.csv").open(encoding="utf-8") as f:
        return {row["alias"].strip().casefold(): row["nama_baku"] for row in csv.DictReader(f)}


@lru_cache
def daftar_kategori() -> list[tuple[re.Pattern, KategoriBarang]]:
    """Keputusan admin (data/referensi/kategori_kata.csv), kata terpanjang dicoba lebih dulu."""
    with (config.DATA_DIR / "referensi" / "kategori_kata.csv").open(encoding="utf-8") as f:
        baris = [(row["kata"].strip().casefold(), KategoriBarang(row["kategori"])) for row in csv.DictReader(f)]
    return [(re.compile(rf"\b{re.escape(k)}\b"), kat) for k, kat in sorted(baris, key=lambda b: -len(b[0]))]


def kategori_dari_daftar(jenis: str) -> KategoriBarang | None:
    teks = jenis.casefold()
    return next((kat for pola, kat in daftar_kategori() if pola.search(teks)), None)


def _beda(a: float, b: float) -> float:
    """Selisih relatif terhadap a."""
    return abs(a - b) / a


def aturan_info_kurang(jenis: str | None, berat_kg: float | None, ada_ukuran: bool, kota: str | None,
                       jalur: Jalur | None, branded: bool | None) -> list[InfoKurang]:
    """Info yang perlu ditanyakan supaya admin bisa memberi harga (aturan admin Pelita):
    - jumlah koli tidak pernah ditanyakan: ukuran/berat total dianggap 1 koli, kecuali pelanggan
      sendiri menyebut ukuran per box dan jumlah box;
    - udara dihitung dari berat (+ branded), laut dari CBM/ukuran;
    - jalur belum disebut: tanyakan jalur, plus berat/ukuran hanya jika dua-duanya belum ada.
    Dipakai validator (prediksi) dan label.info_kurang_dari_label (label), jadi selalu sama.
    """
    kurang = []
    if jenis is None:
        kurang.append(InfoKurang.JENIS_BARANG)
    if jalur is None:
        kurang.append(InfoKurang.JALUR)
        if berat_kg is None and not ada_ukuran:
            kurang += [InfoKurang.BERAT, InfoKurang.DIMENSI_ATAU_CBM]
    elif jalur == Jalur.UDARA:
        if berat_kg is None:
            kurang.append(InfoKurang.BERAT)
        if branded is None:
            kurang.append(InfoKurang.BRANDED)
    elif not ada_ukuran:
        kurang.append(InfoKurang.DIMENSI_ATAU_CBM)
    if kota is None:
        kurang.append(InfoKurang.KOTA_TUJUAN)
    return kurang


def _fmt(sisi: tuple[float, ...]) -> str:
    return "x".join(f"{s:g}" for s in sisi)


def normalisasi(raw: EkstraksiLLM) -> Pesanan:
    peringatan: list[Peringatan] = []

    def peringatkan(kode: KodePeringatan, pesan: str) -> None:
        peringatan.append(Peringatan(kode=kode, pesan=pesan))

    def berat_kg_dari(b: BeratMentah, konteks: str) -> float | None:
        if b.nilai <= 0:
            return None
        satuan = b.satuan
        if satuan is None:
            satuan = SatuanBerat.KG
            peringatkan(KodePeringatan.SATUAN_DIASUMSIKAN, f"{konteks} {b.nilai:g} tanpa satuan, dianggap kg")
        return round(ke_kg(b.nilai, satuan), 3)

    def dimensi_cm_dari(d: DimensiMentah) -> tuple[float, float, float] | None:
        sisi = (d.p, d.l, d.t)
        if min(sisi) <= 0:
            return None
        satuan = d.satuan
        if satuan is None:
            satuan = SatuanPanjang.CM
            peringatkan(KodePeringatan.SATUAN_DIASUMSIKAN, f"dimensi {_fmt(sisi)} tanpa satuan, dianggap cm")
        p, l, t = (round(ke_cm(s, satuan), 2) for s in sisi)
        return p, l, t

    # 1. Grup koli dalam kg dan cm.
    grup = [
        GrupKoli(
            jumlah_koli=g.jumlah_koli if g.jumlah_koli and g.jumlah_koli > 0 else None,
            dimensi_cm=dimensi_cm_dari(g.dimensi_per_koli) if g.dimensi_per_koli else None,
            berat_per_koli_kg=berat_kg_dari(g.berat_per_koli, "berat per koli") if g.berat_per_koli else None,
        )
        for g in raw.grup_koli
    ]
    # Model kadang menulis grup yang semua isinya null; itu bukan informasi.
    grup = [g for g in grup if g.jumlah_koli or g.dimensi_cm or g.berat_per_koli_kg]
    lengkap = bool(grup) and all(g.jumlah_koli for g in grup)

    # 2. Jumlah koli dan berat. Berat total yang disebut didahulukan.
    jumlah_koli = sum(g.jumlah_koli for g in grup) if lengkap else None
    berat_total = berat_kg_dari(raw.berat_total, "berat total") if raw.berat_total else None
    berat_dari_koli = (
        round(sum(g.jumlah_koli * g.berat_per_koli_kg for g in grup), 3)
        if lengkap and all(g.berat_per_koli_kg for g in grup)
        else None
    )
    berat_kg = berat_total if berat_total is not None else berat_dari_koli
    if berat_total and berat_dari_koli and _beda(berat_total, berat_dari_koli) > TOLERANSI_BERAT:
        peringatkan(
            KodePeringatan.BERAT_TIDAK_KONSISTEN,
            f"berat total {berat_total:g} kg, tapi per koli x jumlah = {berat_dari_koli:g} kg",
        )

    # 3. CBM: dari dimensi jika semua grup lengkap, jika tidak dari yang disebut.
    cbm_disebut = raw.cbm_disebut if raw.cbm_disebut and raw.cbm_disebut > 0 else None
    cbm_hitung = (
        round(sum(hitung_cbm(g.jumlah_koli, *g.dimensi_cm) for g in grup), 3)
        if lengkap and all(g.dimensi_cm for g in grup)
        else None
    )
    if cbm_hitung:
        cbm, cbm_sumber = cbm_hitung, "dihitung"
        if cbm_disebut and _beda(cbm_hitung, cbm_disebut) > TOLERANSI_CBM:
            peringatkan(KodePeringatan.CBM_TIDAK_COCOK, f"CBM disebut {cbm_disebut:g}, dari dimensi {cbm_hitung:g}")
    elif cbm_disebut:
        cbm, cbm_sumber = cbm_disebut, "disebut"
    else:
        cbm, cbm_sumber = None, None

    # 4. Cek wajar.
    for g in grup:
        if g.dimensi_cm and not all(SISI_MIN_CM <= s <= SISI_MAKS_CM for s in g.dimensi_cm):
            peringatkan(
                KodePeringatan.DIMENSI_TIDAK_WAJAR,
                f"dimensi {_fmt(g.dimensi_cm)} cm di luar {SISI_MIN_CM}-{SISI_MAKS_CM} cm per sisi",
            )
        if g.berat_per_koli_kg and g.berat_per_koli_kg > BERAT_MAKS_PER_KOLI_KG:
            peringatkan(KodePeringatan.BERAT_TIDAK_WAJAR, f"{g.berat_per_koli_kg:g} kg per koli")
    if berat_kg and jumlah_koli and not any(g.berat_per_koli_kg for g in grup):
        rata = berat_kg / jumlah_koli
        if rata > BERAT_MAKS_PER_KOLI_KG:
            peringatkan(KodePeringatan.BERAT_TIDAK_WAJAR, f"rata-rata {rata:.0f} kg per koli")
    if berat_kg and cbm:
        densitas = berat_kg / cbm
        if not DENSITAS_MIN <= densitas <= DENSITAS_MAKS:
            peringatkan(KodePeringatan.DENSITAS_JANGGAL, f"{densitas:.0f} kg/m3, cek satuan berat dan dimensi")

    # 5. Minimum tarif.
    if raw.jalur == Jalur.LAUT and cbm and cbm < MIN_CBM_LAUT:
        peringatkan(KodePeringatan.DI_BAWAH_MINIMUM, f"{cbm:g} CBM, minimum laut {MIN_CBM_LAUT:g} CBM")
    if raw.jalur == Jalur.UDARA and berat_kg and berat_kg < MIN_KG_UDARA:
        peringatkan(KodePeringatan.DI_BAWAH_MINIMUM, f"{berat_kg:g} kg, minimum udara {MIN_KG_UDARA} kg")

    # 6. Kota.
    kota = None
    if raw.kota_tujuan and raw.kota_tujuan.strip():
        teks = raw.kota_tujuan.strip()
        kota = alias_kota().get(teks.casefold())
        if kota is None:
            kota = teks
            peringatkan(KodePeringatan.KOTA_TIDAK_DIKENAL, f"'{teks}' tidak ada di data/referensi/kota.csv")

    # 7. Info yang kurang.
    jenis = raw.jenis_barang.strip().lower() if raw.jenis_barang and raw.jenis_barang.strip() else None
    ada_ukuran = any(g.dimensi_cm for g in grup) or cbm_disebut is not None
    info_kurang = aturan_info_kurang(jenis, berat_kg, ada_ukuran, kota, raw.jalur, raw.branded)

    # 8. Kategori adalah keputusan admin. Barang yang ada di daftar admin memakai kategori daftar;
    #    selain itu tebakan model dipakai sebagai saran dan ditandai untuk dicek.
    kategori = raw.kategori_barang
    if jenis:
        dari_daftar = kategori_dari_daftar(jenis)
        if dari_daftar:
            kategori = dari_daftar
        else:
            tebakan = kategori.value if kategori else "belum bisa ditebak"
            peringatkan(KodePeringatan.KATEGORI_PERLU_DICEK,
                        f"'{jenis}' belum ada di daftar admin; tebakan model: {tebakan}")

    return Pesanan(
        jenis_barang=jenis,
        kategori_barang=kategori,
        branded=raw.branded,
        jumlah_koli=jumlah_koli,
        berat_kg=berat_kg,
        grup_koli=grup,
        cbm=cbm,
        kota_tujuan=kota,
        jalur=raw.jalur,
        info_kurang=info_kurang,
        cbm_sumber=cbm_sumber,
        bahasa_pelanggan=raw.bahasa_pelanggan,
        peringatan=peringatan,
    )
