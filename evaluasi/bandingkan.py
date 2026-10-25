"""Bandingkan beberapa run (mis. prompt v1 vs v2 vs v3): akurasi per kolom, dan chat yang
berubah salah -> benar atau benar -> salah antara run pertama dan terakhir.

    python -m evaluasi.bandingkan hasil/<run_a> hasil/<run_b> [hasil/<run_c> ...]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluasi.metrik import KOLOM, akurasi


def muat_status(folder: Path) -> dict[str, dict[str, str]]:
    with (folder / "prediksi.jsonl").open(encoding="utf-8") as f:
        return {d["id"]: d["status"] for d in map(json.loads, f)}


def berubah(awal: dict[str, dict[str, str]], akhir: dict[str, dict[str, str]]) -> list[tuple[str, str, str]]:
    """(id, kolom, 'membaik' | 'memburuk') untuk kolom yang statusnya berganti benar <-> tidak benar."""
    hasil = []
    for cid in sorted(awal.keys() & akhir.keys()):
        for kolom in KOLOM:
            a, b = awal[cid][kolom], akhir[cid][kolom]
            if "diabaikan" in (a, b) or (a == "benar") == (b == "benar"):
                continue
            hasil.append((cid, kolom, "membaik" if b == "benar" else "memburuk"))
    return hasil


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", nargs="+", type=Path)
    args = parser.parse_args()
    runs = [muat_status(r) for r in args.run]
    prompt = [json.loads((r / "metrics.json").read_text(encoding="utf-8"))["prompt"] for r in args.run]
    # Prompt yang sama bisa muncul dua kali (mis. setelah skema berubah), jadi diberi nomor run.
    nama = [f"{i}:{p}" for i, p in enumerate(prompt, start=1)]
    for n, r in zip(nama, args.run):
        print(f"{n:<6} {r.name}")
    print()

    lebar = max(8, *(len(n) + 2 for n in nama))
    print(f"{'kolom':<16}" + "".join(f"{n:>{lebar}}" for n in nama))
    for kolom in KOLOM:
        nilai = [akurasi([s[kolom] for s in run.values()]) for run in runs]
        print(f"{kolom:<16}" + "".join(f"{'-' if v is None else f'{v:.0%}':>{lebar}}" for v in nilai))
    semua = [sum(all(v in ("benar", "diabaikan") for v in s.values()) for s in run.values()) for run in runs]
    print(f"{'chat semua benar':<16}" + "".join(f"{f'{x}/{len(run)}':>{lebar}}" for x, run in zip(semua, runs)))

    perubahan = berubah(runs[0], runs[-1])
    print(f"\n{nama[0]} -> {nama[-1]}:")
    for cid, kolom, arah in perubahan:
        print(f"  {arah:<9} {cid} {kolom}")
    if not perubahan:
        print("  tidak ada kolom yang berubah")


if __name__ == "__main__":
    main()
