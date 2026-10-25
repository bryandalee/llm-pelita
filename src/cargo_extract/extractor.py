"""Chat -> EkstraksiLLM lewat Ollama lokal (structured output dengan skema Pydantic)."""
from __future__ import annotations

import json

import ollama

from . import cache, config
from .schemas import EkstraksiLLM

SKEMA = EkstraksiLLM.model_json_schema()


def muat_prompt(versi: str) -> str:
    """Isi prompts/<versi>_*.md."""
    cocok = sorted(config.PROMPTS_DIR.glob(f"{versi}_*.md"))
    if len(cocok) != 1:
        raise FileNotFoundError(f"harus ada tepat satu prompts/{versi}_*.md, ketemu {len(cocok)}")
    return cocok[0].read_text(encoding="utf-8")


def _system_dan_kunci(teks_chat: str, versi_prompt: str, model: str) -> tuple[str, str]:
    # Skema juga ditaruh di prompt (anjuran dokumentasi Ollama): `format` hanya membatasi
    # bentuk JSON, sedangkan deskripsi kolom baru terbaca model kalau ada di teks.
    system = muat_prompt(versi_prompt) + "\nSkema JSON:\n" + json.dumps(SKEMA, ensure_ascii=False)
    return system, cache.kunci(versi_prompt, system, model, teks_chat)


def dari_cache(teks_chat: str, versi_prompt: str, model: str = config.MODEL_ID) -> EkstraksiLLM | None:
    """Hasil yang sudah pernah dihitung, tanpa memanggil model."""
    isi = cache.ambil(_system_dan_kunci(teks_chat, versi_prompt, model)[1])
    return EkstraksiLLM.model_validate_json(isi) if isi else None


def ekstrak(teks_chat: str, versi_prompt: str, model: str = config.MODEL_ID) -> EkstraksiLLM:
    system, k = _system_dan_kunci(teks_chat, versi_prompt, model)
    isi = cache.ambil(k)
    if isi is None:
        res = ollama.Client(host=config.OLLAMA_HOST).chat(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": teks_chat}],
            format=SKEMA,
            think=False,
            options={"temperature": 0},
        )
        isi = res.message.content
        cache.simpan(k, isi)
    return EkstraksiLLM.model_validate_json(isi)
