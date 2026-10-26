"""Estimasi ongkir dari pricelist Pelita (data/referensi/tarif.csv). Dihitung kode, bukan LLM.

Aturan admin Pelita:
- laut: CBM x tarif kategori, minimum 0,1 CBM. Ukuran tanpa jumlah koli dianggap 1 koli.
- udara: berat asli (kg) x tarif branded/non-branded, minimum 3 kg. Ukuran dipakai untuk cek berat
  volume (p x l x t / 6000 per koli): jika lebih besar dari berat, selisihnya ditagih 1/2 tarif per kg.
- harga sudah all-in sampai Jakarta; antar gratis hanya di Jakarta untuk kiriman >= 1 CBM.
  Selain itu ongkir lokal dari Jakarta dihitung terpisah (tergantung ekspedisi lokal).
Hasilnya estimasi: harga khusus (mis. diskon kiriman besar) tetap keputusan admin.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from functools import lru_cache

from . import config
from .satuan import cbm as hitung_cbm
from .schemas import Jalur, KodePeringatan, Pesanan
from .validator import MIN_CBM_LAUT, MIN_KG_UDARA

CBM_ANTAR_GRATIS = 1.0
PEMBAGI_VOLUME = 6000


@dataclass
class Estimasi:
    jalur: Jalur
    golongan: str            # kategori laut, atau "branded"/"non_branded"
    jumlah: float            # CBM atau kg yang ditagih (sudah termasuk minimum)
    satuan: str              # "cbm" atau "kg"
    tarif: int
    perlu_cek: bool = False  # kategori/branded masih tebakan, admin harus memastikan
    catatan: list[str] = field(default_factory=list)
    selisih_volume_kg: float = 0.0   # udara: berat volume di atas berat ditagih setengah tarif

    @property
    def total(self) -> int:
        return round(self.jumlah * self.tarif + self.selisih_volume_kg * self.tarif / 2)


@lru_cache
def tarif() -> dict[tuple[str, str], int]:
    with (config.DATA_DIR / "referensi" / "tarif.csv").open(encoding="utf-8") as f:
        return {(r["jalur"], r["golongan"]): int(r["tarif"]) for r in csv.DictReader(f)}


def _cbm_ditagih(pesanan: Pesanan) -> tuple[float | None, list[str]]:
    if pesanan.cbm:
        return pesanan.cbm, []
    grup = [g for g in pesanan.grup_koli if g.dimensi_cm]
    if not grup:
        return None, []
    catatan = ["jumlah koli tidak disebut, dianggap 1 koli"] if any(not g.jumlah_koli for g in grup) else []
    return round(sum(hitung_cbm(g.jumlah_koli or 1, *g.dimensi_cm) for g in grup), 3), catatan


def berat_volume(pesanan: Pesanan) -> float | None:
    """Total p x l x t / 6000 (kg) dari ukuran per koli; koli tidak disebut dianggap 1."""
    grup = [g for g in pesanan.grup_koli if g.dimensi_cm]
    if not grup:
        return None
    return round(sum((g.jumlah_koli or 1) * g.dimensi_cm[0] * g.dimensi_cm[1] * g.dimensi_cm[2]
                     for g in grup) / PEMBAGI_VOLUME, 2)


def estimasi_harga(pesanan: Pesanan) -> list[Estimasi]:
    """Satu estimasi per pilihan yang bisa dihitung; jalur belum disebut = laut dan udara."""
    hasil = []
    jalur = [pesanan.jalur] if pesanan.jalur else [Jalur.LAUT, Jalur.UDARA]
    kategori_dicek = any(p.kode == KodePeringatan.KATEGORI_PERLU_DICEK for p in pesanan.peringatan)

    if Jalur.LAUT in jalur and pesanan.kategori_barang:
        cbm, catatan = _cbm_ditagih(pesanan)
        if cbm:
            if cbm < MIN_CBM_LAUT:
                catatan.append(f"{cbm:g} CBM di bawah minimum, dihitung {MIN_CBM_LAUT:g} CBM")
                cbm = MIN_CBM_LAUT
            kategori = pesanan.kategori_barang.value
            hasil.append(Estimasi(Jalur.LAUT, kategori, cbm, "cbm", tarif()[("laut", kategori)],
                                  perlu_cek=kategori_dicek, catatan=catatan))

    if Jalur.UDARA in jalur and pesanan.berat_kg:
        kg, catatan = pesanan.berat_kg, []
        if kg < MIN_KG_UDARA:
            catatan.append(f"{kg:g} kg di bawah minimum, dihitung {MIN_KG_UDARA:g} kg")
            kg = MIN_KG_UDARA
        volume, selisih = berat_volume(pesanan), 0.0
        if volume is None:
            catatan.append("ukuran belum ada, berat volume belum dicek")
        elif volume > kg:
            selisih = round(volume - kg, 2)
            catatan.append(f"berat volume {volume:g} kg > {kg:g} kg: selisih {selisih:g} kg ditagih 1/2 tarif")
        pilihan = {True: ["branded"], False: ["non_branded"], None: ["branded", "non_branded"]}[pesanan.branded]
        for golongan in pilihan:
            hasil.append(Estimasi(Jalur.UDARA, golongan, kg, "kg", tarif()[("udara", golongan)],
                                  perlu_cek=pesanan.branded is None, catatan=list(catatan),
                                  selisih_volume_kg=selisih))
    return hasil


def antar_gratis(pesanan: Pesanan, estimasi: Estimasi) -> bool:
    kota = (pesanan.kota_tujuan or "").casefold()
    return kota.startswith("jakarta") and estimasi.satuan == "cbm" and estimasi.jumlah >= CBM_ANTAR_GRATIS
