"""Ekspor WhatsApp -> episode chat tersamarkan di data/privat/.

    python scripts/impor_whatsapp.py data/raw/ekspor_01/chat.txt --nama Bryan

Keluaran (semuanya tidak di-commit):
- data/privat/<folder>.jsonl            satu DraftChat per episode
- data/privat/<folder>_pratinjau.txt    untuk dibaca dan dicek manual
- data/privat/<folder>_pengganti.json   peta asli -> palsu
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from cargo_extract import config
from cargo_extract.samarkan import samarkan_pesan
from cargo_extract.schemas import DraftChat
from cargo_extract.whatsapp import baca_ekspor, potong_episode


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ekspor", type=Path, help="chat.txt hasil ekspor WhatsApp")
    parser.add_argument("--nama", action="append", default=[], help="nama orang lain yang perlu disamarkan")
    parser.add_argument("--admin", action="append", default=["You", "Anda"], help="nama pengirim di sisi admin")
    args = parser.parse_args()

    sumber = args.ekspor.parent.name
    baca = baca_ekspor(args.ekspor, set(args.admin))
    pesan, pengganti = samarkan_pesan(baca.pesan, baca.nama_pelanggan, args.nama)
    drafts = [
        DraftChat(id=f"{sumber}_ep{i:02d}", sumber=sumber, episode=i, pesan=ep)
        for i, ep in enumerate(potong_episode(pesan), start=1)
    ]

    config.PRIVAT_DIR.mkdir(parents=True, exist_ok=True)
    with (config.PRIVAT_DIR / f"{sumber}.jsonl").open("w", encoding="utf-8") as f:
        for d in drafts:
            f.write(d.model_dump_json() + "\n")
    with (config.PRIVAT_DIR / f"{sumber}_pratinjau.txt").open("w", encoding="utf-8") as f:
        for d in drafts:
            f.write(f"===== {d.id} ({len(d.pesan)} pesan) =====\n")
            for p in d.pesan:
                f.write(f"[{p.waktu:%Y-%m-%d %H:%M}] {p.pengirim}: {p.teks}\n")
            f.write("\n")
    (config.PRIVAT_DIR / f"{sumber}_pengganti.json").write_text(
        json.dumps(pengganti, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{len(pesan)} pesan, {len(drafts)} episode:")
    for d in drafts:
        print(f"  {d.id}: {d.pesan[0].waktu:%Y-%m-%d} s.d. {d.pesan[-1].waktu:%Y-%m-%d}, {len(d.pesan)} pesan")
    jenis = Counter(v.strip("[]").rstrip("0123456789") for v in pengganti.values())
    print("disamarkan:", ", ".join(f"{k} {n}" for k, n in sorted(jenis.items())) or "-")
    print(f"periksa: data/privat/{sumber}_pratinjau.txt")


if __name__ == "__main__":
    main()
