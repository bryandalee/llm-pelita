"""Tahap 2: foto pelanggan -> nama barang singkat (qwen3.5:9b juga bisa membaca gambar).

Hasilnya disisipkan ke teks chat sebagai "[foto: ...]" sebelum ekstraksi biasa, jadi skema dan
validator tidak berubah. Model foto hanya diminta menyebut barang: di screenshot toko, angka yang
terlihat biasanya ukuran produk, bukan ukuran koli, dan bisa terbaca sebagai info kiriman.
Gambar diperkecil dulu; di CPU laptop ini ukuran asli butuh 30-190 detik per foto.
"""
from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

import ollama
from PIL import Image

from . import cache, config
from .schemas import EkstraksiLLM, Pesan

SISI_MAKS = 1024
PROMPT_FOTO = (
    "Ini foto atau screenshot yang dikirim pelanggan jasa cargo China-Indonesia. Sebutkan nama barang "
    "utama yang mau dikirim dalam bahasa Indonesia, maksimal 8 kata, ditambah merek jika tertulis jelas. "
    "Jangan tulis harga, jumlah, berat, atau ukuran. Kalau gambar bukan barang (mis. formulir, chat, "
    "bukti transfer), tulis: bukan foto barang."
)
POLA_PENANDA = re.compile(r"\[foto\]")
POLA_DESKRIPSI = re.compile(r"\[foto: ([^\]]+)\]")
BUKAN_BARANG = "bukan foto barang"


def perkecil(path: Path, sisi: int = SISI_MAKS) -> bytes:
    gambar = Image.open(path).convert("RGB")
    gambar.thumbnail((sisi, sisi))
    buf = io.BytesIO()
    gambar.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def baca_foto(path: Path, model: str = config.MODEL_ID, sisi: int = SISI_MAKS) -> str:
    data = perkecil(path, sisi)
    k = cache.kunci("foto", PROMPT_FOTO, model, str(sisi), hashlib.sha256(data).hexdigest())
    isi = cache.ambil(k)
    if isi is None:
        res = ollama.Client(host=config.OLLAMA_HOST).chat(
            model=model,
            messages=[{"role": "user", "content": PROMPT_FOTO, "images": [data]}],
            think=False,
            options={"temperature": 0, "num_predict": 60},
        )
        isi = " ".join(res.message.content.split()).strip(" .")
        cache.simpan(k, isi)
    return isi


def path_foto(p: Pesan, folder: Path = config.DATA_DIR / "raw") -> list[Path]:
    """File foto pelanggan di pesan ini yang benar-benar ada (ekspor Windows tidak membawa media)."""
    if p.pengirim != "pelanggan":
        return []
    hasil = []
    for lamp in p.lampiran:
        if lamp.jenis == "foto" and lamp.file:
            path = Path(lamp.file) if Path(lamp.file).is_absolute() else folder / lamp.file
            if path.exists():
                hasil.append(path)
    return hasil


def sisipkan_foto(pesan: list[Pesan], folder: Path = config.DATA_DIR / "raw", **opsi) -> list[Pesan]:
    """Ganti penanda "[foto]" di pesan pelanggan dengan "[foto: <barang>]" untuk foto yang filenya ada."""
    hasil = []
    for p in pesan:
        teks = p.teks
        for path in path_foto(p, folder):
            isi = f"[foto: {baca_foto(path, **opsi)}]"
            teks = POLA_PENANDA.sub(isi, teks, count=1) if POLA_PENANDA.search(teks) else f"{teks}\n{isi}"
        hasil.append(p.model_copy(update={"teks": teks}))
    return hasil


def jenis_dari_foto(pesan: list[Pesan]) -> str | None:
    """Deskripsi foto barang pertama di pesan pelanggan (setelah sisipkan_foto)."""
    for p in pesan:
        if p.pengirim != "pelanggan":
            continue
        for isi in POLA_DESKRIPSI.findall(p.teks):
            if BUKAN_BARANG not in isi.casefold():
                return isi.strip()
    return None


def lengkapi_jenis(raw: EkstraksiLLM, pesan: list[Pesan]) -> EkstraksiLLM:
    # Ekstraksi sering mengabaikan "[foto: ...]" saat teks pelanggan tidak menyebut barang
    # (4 dari 4 episode di uji tahap 2), jadi kode yang mengisi jenis dari deskripsi foto.
    if raw.jenis_barang:
        return raw
    jenis = jenis_dari_foto(pesan)
    return raw.model_copy(update={"jenis_barang": jenis}) if jenis else raw
