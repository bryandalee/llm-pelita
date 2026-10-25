"""Pertanyaan balik dari template (id/zh/en), tanpa LLM, supaya bisa diuji.

Aturan bisnis dari admin Pelita:
- satu ukuran tanpa jumlah koli -> konfirmasi "1 koli?" alih-alih menanyakan jumlah koli dari nol;
- branded hanya ditanyakan untuk kiriman udara (sudah diatur di info_kurang).
"""
from __future__ import annotations

import re

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
        "koli_satu": "ukuran {dimensi} cm itu untuk 1 koli ya kak?",
        InfoKurang.JENIS_BARANG: "barangnya apa ya kak? (boleh kirim fotonya)",
        InfoKurang.JUMLAH_KOLI: "ada berapa koli/dus?",
        InfoKurang.BERAT: "berat totalnya kira-kira berapa kg?",
        InfoKurang.DIMENSI_ATAU_CBM: "ukuran per koli (p x l x t, cm) atau total CBM-nya?",
        InfoKurang.KOTA_TUJUAN: "dikirim ke kota mana?",
        InfoKurang.JALUR: "mau dikirim via laut atau udara?",
        InfoKurang.BRANDED: "barangnya bermerek (branded) atau tidak?",
    },
    Bahasa.ZH: {
        "pembuka": "您好，为了计算运费，请提供以下信息：",
        "koli_satu": "尺寸 {dimensi} cm 是一件吗？",
        InfoKurang.JENIS_BARANG: "是什么货物？（也可以发照片）",
        InfoKurang.JUMLAH_KOLI: "一共几件/几箱？",
        InfoKurang.BERAT: "总重量大约多少公斤？",
        InfoKurang.DIMENSI_ATAU_CBM: "每件尺寸（长x宽x高，cm）或总方数？",
        InfoKurang.KOTA_TUJUAN: "寄到印尼哪个城市？",
        InfoKurang.JALUR: "走海运还是空运？",
        InfoKurang.BRANDED: "货物是品牌货吗？",
    },
    Bahasa.EN: {
        "pembuka": "Thank you! To calculate the shipping cost, could you share:",
        "koli_satu": "is the {dimensi} cm size for 1 carton?",
        InfoKurang.JENIS_BARANG: "what are the goods? (a photo is fine)",
        InfoKurang.JUMLAH_KOLI: "how many cartons?",
        InfoKurang.BERAT: "the total weight in kg?",
        InfoKurang.DIMENSI_ATAU_CBM: "the size per carton (L x W x H, cm) or the total CBM?",
        InfoKurang.KOTA_TUJUAN: "the destination city in Indonesia?",
        InfoKurang.JALUR: "sea or air freight?",
        InfoKurang.BRANDED: "are the goods branded?",
    },
}


def buat_pertanyaan(pesanan: Pesanan) -> str | None:
    """None jika tidak ada yang kurang."""
    teks = TEKS[pesanan.bahasa_pelanggan]
    butir = []
    for item in pesanan.info_kurang:
        satu_ukuran = len(pesanan.grup_koli) == 1 and pesanan.grup_koli[0].dimensi_cm
        if item == InfoKurang.JUMLAH_KOLI and satu_ukuran:
            dimensi = "x".join(f"{s:g}" for s in pesanan.grup_koli[0].dimensi_cm)
            butir.append(teks["koli_satu"].format(dimensi=dimensi))
        else:
            butir.append(teks[item])
    if not butir:
        return None
    return teks["pembuka"] + "\n" + "\n".join(f"{i}. {b}" for i, b in enumerate(butir, start=1))
