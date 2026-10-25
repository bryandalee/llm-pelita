"""Jalankan extractor + validator ke episode chat tersamarkan (belum berlabel) dan tampilkan hasilnya.
Jika episode sudah ditandai (app/tandai.py), hanya pesan sebelum titik potong yang dikirim.

    python scripts/coba_draft.py data/privat/ekspor_01.jsonl            # prompt baku, template dibuang
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from cargo_extract import config
from cargo_extract.bersihkan import buang_template
from cargo_extract.dataset import teks_chat
from cargo_extract.extractor import ekstrak
from cargo_extract.tanda import input_episode, muat_draft, muat_tanda
from cargo_extract.validator import normalisasi


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("draft", type=Path)
    parser.add_argument("--prompt", default=config.PROMPT_BAKU)
    parser.add_argument("--model", default=config.MODEL_ID)
    parser.add_argument("--bersihkan", action=argparse.BooleanOptionalAction, default=True,
                        help="buang template admin sebelum dikirim ke model (bawaan: ya)")
    args = parser.parse_args()

    tanda = muat_tanda()
    for d in muat_draft(args.draft):
        t = tanda.get(d.id)
        if t and t.jenis != "permintaan_harga":
            print(f"===== {d.id}: dilewati ({t.jenis}) =====")
            continue
        pesan = input_episode(d, t)
        keterangan = "belum ditandai" if t is None else f"{len(pesan)} dari {len(d.pesan)} pesan"
        if args.bersihkan:
            pesan = buang_template(pesan)
            keterangan += f", {len(pesan)} setelah template dibuang"
        t0 = time.time()
        raw = ekstrak(teks_chat(pesan), args.prompt, args.model)
        pesanan = normalisasi(raw)
        print(f"===== {d.id} ({keterangan}, {time.time() - t0:.0f} detik) =====")
        print(pesanan.model_dump_json(indent=1, exclude={"peringatan"}))
        for p in pesanan.peringatan:
            print(f"! {p.kode.value}: {p.pesan}")
        for c in raw.catatan_ambigu:
            print(f"? {c}")


if __name__ == "__main__":
    main()
