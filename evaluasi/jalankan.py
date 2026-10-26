"""Jalankan extractor + validator ke satu split dan simpan hasil ke hasil/<run_id>/.

    python -m evaluasi.jalankan --split asli-test          # prompt baku, template dibuang
    python -m evaluasi.jalankan --prompt v3 --no-bersihkan --split dev
    python -m evaluasi.jalankan --split asli --riwayat     # + contoh keputusan admin yang mirip

Split:
- dev / test: chat sintetis di data/chats/.
- asli-dev: chat asli yang dipakai selama memperbaiki prompt (daftar di data/privat/split.json).
- asli-test: chat asli lain yang sudah dilabel, tidak dilihat saat tuning. Ini angka yang jujur.
- asli: asli-dev + asli-test.
- foto: chat asli berlabel yang punya file foto pelanggan sebelum titik potong (tahap 2). Jenis barang
  dinilai dengan label setelah melihat foto (data/privat/label_foto.json, dicek pengguna).
Hasil split asli memuat potongan chat asli, jadi disimpan di data/privat/hasil/ (tidak di-commit).
Keluaran: prediksi.jsonl, metrics.json, gagal.csv.

--riwayat: bank contoh = semua chat asli berlabel. Tiap chat hanya melihat contoh dari ekspor
(pelanggan) lain, jadi labelnya sendiri tidak pernah ikut (leave-one-out).
--foto: foto pelanggan dibaca model dan disisipkan ke teks sebagai "[foto: ...]" (lihat foto.py).

    python -m evaluasi.jalankan --split foto               # teks saja, dinilai dengan label foto
    python -m evaluasi.jalankan --split foto --foto --sisi 768
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime

from cargo_extract import config
from cargo_extract.bersihkan import buang_template
from cargo_extract.dataset import format_chat, muat_chats, teks_chat
from cargo_extract.extractor import ekstrak
from cargo_extract.foto import SISI_MAKS, lengkapi_jenis, path_foto, sisipkan_foto
from cargo_extract.label import file_dataset, info_kurang_dari_label, muat_label_foto
from cargo_extract.riwayat import K, bangun_bank, konteks_untuk, sumber
from cargo_extract.validator import normalisasi
from evaluasi.metrik import KOLOM, STATUS, bandingkan_kolom, kolom_diabaikan, ringkas


def chat_asli(split: str) -> list:
    bagian = ["dev", "test"] if split == "asli" else [split.removeprefix("asli-")]
    # info_kurang dihitung ulang dari label, supaya dataset lama tetap memakai aturan terbaru.
    return [c.model_copy(update={"label": c.label.model_copy(update={"info_kurang": info_kurang_dari_label(c.label)})})
            for b in bagian for c in muat_chats(file_dataset(b))]


def chat_foto() -> list:
    """Chat asli dengan foto pelanggan; jenis barang diganti label setelah melihat foto."""
    label_foto = muat_label_foto()
    chats = [c for c in chat_asli("asli") if any(path_foto(p) for p in c.pesan)]
    belum = [c.id for c in chats if c.id not in label_foto]
    if belum:
        raise SystemExit(f"label foto belum dicek untuk {len(belum)} episode: {', '.join(belum)}")
    hasil = []
    for c in chats:
        lab = c.label.model_copy(update={"jenis_barang": label_foto[c.id]})
        lab = lab.model_copy(update={"info_kurang": info_kurang_dari_label(lab)})
        hasil.append(c.model_copy(update={"label": lab}))
    return hasil


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", default=config.PROMPT_BAKU)
    parser.add_argument("--split", choices=["dev", "test", "asli-dev", "asli-test", "asli", "foto"], default="dev")
    parser.add_argument("--model", default=config.MODEL_ID)
    parser.add_argument("--bersihkan", action=argparse.BooleanOptionalAction, default=True,
                        help="buang template admin sebelum dikirim ke model (bawaan: ya)")
    parser.add_argument("--riwayat", action="store_true",
                        help="tambahkan contoh keputusan admin dari chat asli lain yang mirip")
    parser.add_argument("--k", type=int, default=K, help="jumlah contoh riwayat; 0 = semua")
    parser.add_argument("--foto", action="store_true", help="baca foto pelanggan dan sisipkan ke teks")
    parser.add_argument("--sisi", type=int, default=SISI_MAKS, help="sisi terpanjang gambar (px) untuk --foto")
    args = parser.parse_args()

    nama_prompt = args.prompt + ("-bersih" if args.bersihkan else "")
    if args.riwayat:
        nama_prompt += f"+riwayat{args.k or '-semua'}"
    if args.foto:
        nama_prompt += f"+foto{args.sisi}"
    run_id = f"{datetime.now():%Y%m%d-%H%M%S}_{nama_prompt}_{args.split}_{args.model.replace(':', '-')}"
    if args.split.startswith("asli") or args.split == "foto":
        chats = chat_foto() if args.split == "foto" else chat_asli(args.split)
        folder = config.PRIVAT_DIR / "hasil" / run_id
    else:
        chats = muat_chats(config.DATA_DIR / "chats" / f"{args.split}.jsonl")
        folder = config.ROOT / "hasil" / run_id
    folder.mkdir(parents=True)
    bank = bangun_bank(chat_asli("asli")) if args.riwayat else []

    pasangan, abaikan, gagal = [], [], []
    with (folder / "prediksi.jsonl").open("w", encoding="utf-8") as f:
        for c in chats:
            t0 = time.time()
            pesan = buang_template(c.pesan) if args.bersihkan else c.pesan
            if args.foto:
                pesan = sisipkan_foto(pesan, model=args.model, sisi=args.sisi)
            teks = teks_chat(pesan) if args.bersihkan else format_chat(c.model_copy(update={"pesan": pesan}))
            konteks = konteks_untuk(c.pesan, bank, kecuali_sumber=sumber(c.id), k=args.k) if args.riwayat else ""
            raw = ekstrak(teks, args.prompt, args.model, konteks)
            if args.foto:
                raw = lengkapi_jenis(raw, pesan)
            pred = normalisasi(raw)
            detik = time.time() - t0
            status = bandingkan_kolom(c.label, pred, kolom_diabaikan(c))
            pasangan.append((c.label, pred))
            abaikan.append(kolom_diabaikan(c))
            f.write(json.dumps({
                "id": c.id,
                "detik": round(detik, 1),
                "status": status,
                "konteks": konteks,
                **({"teks_input": teks} if args.foto else {}),
                "mentah": raw.model_dump(mode="json"),
                "pesanan": pred.model_dump(mode="json"),
            }, ensure_ascii=False) + "\n")
            label_json, pred_json = c.label.model_dump(mode="json"), pred.model_dump(mode="json")
            for kolom, s in status.items():
                if s not in ("benar", "diabaikan"):
                    gagal.append({
                        "id": c.id, "kolom": kolom, "status": s,
                        "label": json.dumps(label_json[kolom], ensure_ascii=False),
                        "prediksi": json.dumps(pred_json[kolom], ensure_ascii=False),
                    })
            benar = sum(s == "benar" for s in status.values())
            dinilai = sum(s != "diabaikan" for s in status.values())
            print(f"{c.id}: {detik:.0f} detik, {benar}/{dinilai} kolom benar", flush=True)

    metrics = ringkas(pasangan, abaikan) | {
        "prompt": nama_prompt,
        "split": args.split, "model": args.model, "bersihkan": args.bersihkan, "riwayat": args.riwayat,
        "foto": args.foto, "sisi": args.sisi if args.foto else None,
    }
    (folder / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    # utf-8-sig supaya Excel membaca huruf Mandarin dengan benar.
    with (folder / "gagal.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "kolom", "status", "label", "prediksi"])
        writer.writeheader()
        writer.writerows(gagal)

    print(f"\nHasil: {folder.relative_to(config.ROOT)}")
    print(f"{'kolom':<16}" + "".join(f"{s:>12}" for s in STATUS))
    for kolom in KOLOM:
        m = metrics["per_kolom"][kolom]
        print(f"{kolom:<16}" + "".join(f"{m[s]:>12}" for s in STATUS))
    print(f"chat yang semua kolomnya benar: {metrics['chat_semua_benar']}/{metrics['jumlah_chat']}")


if __name__ == "__main__":
    main()
