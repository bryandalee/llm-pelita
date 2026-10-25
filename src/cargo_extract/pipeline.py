"""Chat -> Pesanan lengkap: buang template -> extractor -> validator -> pertanyaan balik."""
from __future__ import annotations

from . import config
from .bersihkan import buang_template
from .dataset import teks_chat
from .extractor import ekstrak
from .pertanyaan import bahasa_balasan, buat_pertanyaan
from .schemas import EkstraksiLLM, Pesan, Pesanan
from .validator import normalisasi


def proses(
    pesan: list[Pesan], versi_prompt: str = config.PROMPT_BAKU, model: str = config.MODEL_ID
) -> tuple[Pesanan, EkstraksiLLM]:
    """Kembalikan pesanan final dan output mentah model (untuk ditampilkan/diperiksa)."""
    raw = ekstrak(teks_chat(buang_template(pesan)), versi_prompt, model)
    # Bahasa balasan dihitung dari pesan pelanggan; tebakan model kurang andal untuk chat campuran.
    pesanan = normalisasi(raw).model_copy(update={"bahasa_pelanggan": bahasa_balasan(pesan)})
    return pesanan.model_copy(update={"pertanyaan_balik": buat_pertanyaan(pesanan)}), raw
