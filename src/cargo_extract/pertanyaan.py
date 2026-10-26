"""Draf balasan dari template (id/zh/en), tanpa LLM, supaya bisa diuji.

Isinya estimasi harga (harga.py) jika bisa dihitung, lalu pertanyaan untuk info yang kurang.
Yang ditanyakan mengikuti aturan admin Pelita di validator.aturan_info_kurang (mis. jumlah koli
tidak pernah ditanyakan; branded hanya untuk udara).
"""
from __future__ import annotations

import re

from .harga import Estimasi, antar_gratis
from .schemas import Bahasa, InfoKurang, Pesan, Pesanan

POLA_CJK = re.compile(r"[一-鿿]")
POLA_LATIN = re.compile(r"[A-Za-z]")
KATA_EN = {"the", "please", "how", "much", "ship", "want", "is", "are", "to", "from", "price", "can",
           "you", "i", "my", "we", "need", "cost", "send", "hi", "hello"}
KATA_ID = {"kak", "mau", "kirim", "berapa", "brp", "ya", "dari", "ke", "barang", "bisa", "saya", "aku",
           "ini", "itu", "dan", "untuk", "sudah", "tidak", "apa", "gimana", "halo", "salah", "aja"}


def bahasa_balasan(pesan: list[Pesan]) -> Bahasa:
    """Bahasa dominan pesan pelanggan, dihitung kode (bukan ditebak model).

    Mandarin hanya jika huruf Han cukup dominan (satu huruf Han ~ satu kata); chat campuran seperti
    "3 ctn, 每箱 60*40*35, 15公斤, eh salah 4 ctn ya" tetap dibalas bahasa Indonesia.
    """
    teks = " ".join(p.teks for p in pesan if p.pengirim == "pelanggan")
    if len(POLA_CJK.findall(teks)) * 3 >= max(len(POLA_LATIN.findall(teks)), 1):
        return Bahasa.ZH
    kata = re.findall(r"[a-z]+", teks.lower())
    en, id_ = sum(k in KATA_EN for k in kata), sum(k in KATA_ID for k in kata)
    return Bahasa.EN if en > id_ else Bahasa.ID

TEKS = {
    Bahasa.ID: {
        "pembuka": "Baik kak, untuk menghitung ongkirnya boleh dibantu info berikut:",
        "pembuka_harga": "Baik kak, estimasi ongkirnya:",
        "lanjut": "Untuk lanjut, boleh dibantu info berikut:",
        "allin": "Harga sudah all-in sampai Jakarta.",
        "lokal": "Pengiriman dari Jakarta ke {kota} lewat ekspedisi lokal, biayanya terpisah ya kak.",
        "lokal_tanpa_kota": "Pengiriman dari Jakarta ke alamat kakak lewat ekspedisi lokal, biayanya terpisah ya kak.",
        "gratis": "Sudah termasuk antar ke alamat di Jakarta.",
        "laut": "Via laut", "udara": "Via udara",
        InfoKurang.JENIS_BARANG: "barangnya apa ya kak? (boleh kirim fotonya)",
        InfoKurang.BERAT: "berat totalnya kira-kira berapa kg?",
        InfoKurang.DIMENSI_ATAU_CBM: "ukurannya (p x l x t, cm) atau total CBM-nya?",
        InfoKurang.KOTA_TUJUAN: "dikirim ke kota mana?",
        InfoKurang.JALUR: "mau dikirim via laut atau udara?",
        InfoKurang.BRANDED: "barangnya bermerek (branded) atau tidak?",
    },
    Bahasa.ZH: {
        "pembuka": "您好，为了计算运费，请提供以下信息：",
        "pembuka_harga": "您好，运费估算如下：",
        "lanjut": "另外请提供以下信息：",
        "allin": "价格包含到雅加达的所有费用。",
        "lokal": "从雅加达到{kota}由当地快递配送，运费另计。",
        "lokal_tanpa_kota": "从雅加达到您地址由当地快递配送，运费另计。",
        "gratis": "已包含雅加达市内送货。",
        "laut": "海运", "udara": "空运",
        InfoKurang.JENIS_BARANG: "是什么货物？（也可以发照片）",
        InfoKurang.BERAT: "总重量大约多少公斤？",
        InfoKurang.DIMENSI_ATAU_CBM: "尺寸（长x宽x高，cm）或总方数？",
        InfoKurang.KOTA_TUJUAN: "寄到印尼哪个城市？",
        InfoKurang.JALUR: "走海运还是空运？",
        InfoKurang.BRANDED: "货物是品牌货吗？",
    },
    Bahasa.EN: {
        "pembuka": "Thank you! To calculate the shipping cost, could you share:",
        "pembuka_harga": "Thank you! Estimated shipping cost:",
        "lanjut": "To continue, could you share:",
        "allin": "All-in price up to Jakarta.",
        "lokal": "Delivery from Jakarta to {kota} goes through a local courier, charged separately.",
        "lokal_tanpa_kota": "Delivery from Jakarta to your address goes through a local courier, charged separately.",
        "gratis": "Includes delivery to your address in Jakarta.",
        "laut": "Sea freight", "udara": "Air freight",
        InfoKurang.JENIS_BARANG: "what are the goods? (a photo is fine)",
        InfoKurang.BERAT: "the total weight in kg?",
        InfoKurang.DIMENSI_ATAU_CBM: "the size (L x W x H, cm) or the total CBM?",
        InfoKurang.KOTA_TUJUAN: "the destination city in Indonesia?",
        InfoKurang.JALUR: "sea or air freight?",
        InfoKurang.BRANDED: "are the goods branded?",
    },
}
GOLONGAN = {
    Bahasa.ID: {"tas": "tas", "umum": "umum", "lartas_ringan": "lartas ringan", "lartas_berat": "lartas berat",
                "semi_garmen": "semi garmen", "garmen": "garmen", "branded": "branded", "non_branded": "non-branded"},
    Bahasa.ZH: {"tas": "箱包", "umum": "普货", "lartas_ringan": "轻敏感货", "lartas_berat": "重敏感货",
                "semi_garmen": "半成衣", "garmen": "成衣", "branded": "品牌货", "non_branded": "非品牌货"},
    Bahasa.EN: {"tas": "bags", "umum": "general", "lartas_ringan": "restricted (light)",
                "lartas_berat": "restricted (heavy)", "semi_garmen": "semi-garment", "garmen": "garment",
                "branded": "branded", "non_branded": "non-branded"},
}


def rupiah(n: float) -> str:
    return "Rp" + f"{round(n):,}".replace(",", ".")


def _angka(x: float, bahasa: Bahasa) -> str:
    teks = f"{x:g}"
    return teks.replace(".", ",") if bahasa == Bahasa.ID else teks


def _baris_harga(e: Estimasi, bahasa: Bahasa) -> str:
    teks = TEKS[bahasa]
    hitung = f"{_angka(e.jumlah, bahasa)} {e.satuan.upper() if e.satuan == 'cbm' else 'kg'} × {rupiah(e.tarif)}"
    if e.selisih_volume_kg:
        hitung += f" + {_angka(e.selisih_volume_kg, bahasa)} kg × {rupiah(e.tarif / 2)}"
    return f"- {teks[e.jalur.value]} ({GOLONGAN[bahasa][e.golongan]}): {hitung} = {rupiah(e.total)}"


def buat_pertanyaan(pesanan: Pesanan) -> str | None:
    """Hanya pertanyaan untuk info yang kurang; None jika tidak ada yang kurang."""
    return buat_balasan(pesanan, [])


def buat_balasan(pesanan: Pesanan, estimasi: list[Estimasi]) -> str | None:
    """Draf balasan: estimasi harga (jika ada), lalu pertanyaan info yang kurang. None jika kosong."""
    teks = TEKS[pesanan.bahasa_pelanggan]
    bagian = []
    if estimasi:
        baris = [teks["pembuka_harga"], *(_baris_harga(e, pesanan.bahasa_pelanggan) for e in estimasi), teks["allin"]]
        if all(antar_gratis(pesanan, e) for e in estimasi):
            baris.append(teks["gratis"])
        elif pesanan.kota_tujuan:
            baris.append(teks["lokal"].format(kota=pesanan.kota_tujuan))
        else:
            baris.append(teks["lokal_tanpa_kota"])
        bagian.append("\n".join(baris))
    butir = [teks[item] for item in pesanan.info_kurang if item in teks]
    if butir:
        pembuka = teks["lanjut"] if estimasi else teks["pembuka"]
        bagian.append(pembuka + "\n" + "\n".join(f"{i}. {b}" for i, b in enumerate(butir, start=1)))
    return "\n\n".join(bagian) or None
