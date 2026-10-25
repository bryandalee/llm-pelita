"""Konfigurasi dari .env (lihat .env.example)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL_ID = os.getenv("MODEL_ID", "qwen3.5:9b")
# Prompt baku. v6 dibekukan sebelum test chat asli dibuat; v7 (v6 + tabel kategori Pelita) diuji
# sekali di test dan lebih baik (25 Okt 2026). Eksperimen baru pakai versi prompt baru lewat --prompt,
# dan sebaiknya diuji di chat test BARU, karena test sekarang sudah dipakai dua kali.
PROMPT_BAKU = "v7"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or None

PROMPTS_DIR = ROOT / "prompts"
DATA_DIR = ROOT / "data"
PRIVAT_DIR = DATA_DIR / "privat"   # chat asli tersamarkan; tidak di-commit
CACHE_DIR = ROOT / ".cache"
