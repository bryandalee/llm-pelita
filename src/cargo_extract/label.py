"""Label manual episode chat asli (data/privat/label.json) dan pembangun dataset evaluasinya.

Dataset dibangun ulang dari draft + tanda + label setiap kali label disimpan, ke
data/privat/dataset/asli_{dev,test}.jsonl (satu ContohChat per episode 'permintaan_harga' yang
sudah dilabel). Episode yang tercantum di data/privat/split.json masuk dev, sisanya test.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config
from .schemas import ContohChat, InfoKurang, LabelManual, LabelPesanan, MetaChat
from .tanda import input_episode, muat_draft, muat_tanda
from .validator import aturan_info_kurang

# Sama dengan tabel tag di docs/panduan_label.md.
TAGS = [
    "revisi", "per_koli", "berat_total", "pcs_bukan_koli", "satuan_jin", "satuan_meter",
    "satuan_tidak_tertulis", "cbm_disebut", "kota_mandarin", "kota_singkatan", "campur_bahasa",
    "multi_grup", "ada_gambar", "packing_list", "kategori_perlu_dicek", "perkiraan",
    "info_setelah_potong", "formulir", "pengandaian", "rentang",
]


def file_label() -> Path:
    return config.PRIVAT_DIR / "label.json"


def file_draft_label() -> Path:
    """Usulan label yang belum diverifikasi (mis. dari Claude); dipakai sebagai isian awal halaman label."""
    return config.PRIVAT_DIR / "draft_label.json"


def file_split() -> Path:
    """{"dev": [id, ...]}: episode asli yang sudah dipakai untuk memperbaiki prompt."""
    return config.PRIVAT_DIR / "split.json"


def id_dev() -> set[str]:
    path = file_split()
    return set(json.loads(path.read_text(encoding="utf-8"))["dev"]) if path.exists() else set()


def file_dataset(split: str) -> Path:
    """split 'dev' (dipakai saat tuning) atau 'test' (episode berlabel lainnya)."""
    return config.PRIVAT_DIR / "dataset" / f"asli_{split}.jsonl"


def muat_label(path: Path | None = None) -> dict[str, LabelManual]:
    path = path or file_label()
    if not path.exists():
        return {}
    return {k: LabelManual.model_validate(v) for k, v in json.loads(path.read_text(encoding="utf-8")).items()}


def simpan_label(id_episode: str, label: LabelManual, path: Path | None = None) -> None:
    path = path or file_label()
    semua = muat_label(path) | {id_episode: label}
    path.parent.mkdir(parents=True, exist_ok=True)
    isi = {k: v.model_dump(mode="json") for k, v in sorted(semua.items())}
    path.write_text(json.dumps(isi, ensure_ascii=False, indent=2), encoding="utf-8")


def file_label_foto(draft: bool = False) -> Path:
    """Tahap 2: {id: jenis barang setelah melihat foto}. draft=True: usulan yang belum dicek pengguna."""
    return config.PRIVAT_DIR / ("draft_label_foto.json" if draft else "label_foto.json")


def muat_label_foto(path: Path | None = None) -> dict[str, str | None]:
    path = path or file_label_foto()
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def simpan_label_foto(id_episode: str, jenis: str | None, path: Path | None = None) -> None:
    path = path or file_label_foto()
    semua = muat_label_foto(path) | {id_episode: jenis}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(semua.items())), ensure_ascii=False, indent=2), encoding="utf-8")


def info_kurang_dari_label(lab: LabelPesanan) -> list[InfoKurang]:
    """Aturan 'Info kurang' (validator.aturan_info_kurang), diterapkan ke isian label."""
    ada_ukuran = any(g.dimensi_cm for g in lab.grup_koli) or lab.cbm is not None
    return aturan_info_kurang(lab.jenis_barang, lab.berat_kg, ada_ukuran, lab.kota_tujuan, lab.jalur, lab.branded)


def bangun_dataset() -> tuple[dict[str, int], list[str]]:
    """Tulis ulang dataset asli (dev + test).

    Kembalikan ({split: jumlah contoh}, id yang titik potongnya berubah sejak dilabel).
    """
    tanda, label, dev = muat_tanda(), muat_label(), id_dev()
    drafts = {d.id: d for f in sorted(config.PRIVAT_DIR.glob("*.jsonl")) for d in muat_draft(f)}
    contoh: dict[str, list[ContohChat]] = {"dev": [], "test": []}
    berubah = []
    for id_ep, lm in sorted(label.items()):
        t = tanda.get(id_ep)
        if id_ep not in drafts or t is None or t.jenis != "permintaan_harga":
            continue
        if t.potong_sebelum != lm.potong_sebelum:
            berubah.append(id_ep)
        contoh["dev" if id_ep in dev else "test"].append(ContohChat(
            id=id_ep,
            pesan=input_episode(drafts[id_ep], t),
            # info_kurang dihitung ulang supaya selalu mengikuti aturan terbaru.
            label=lm.label.model_copy(update={"info_kurang": info_kurang_dari_label(lm.label)}),
            meta=MetaChat(bahasa=lm.bahasa, sumber="disamarkan", tag=lm.tag),
        ))
    for split, daftar in contoh.items():
        path = file_dataset(split)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(c.model_dump_json() + "\n" for c in daftar), encoding="utf-8")
    return {split: len(daftar) for split, daftar in contoh.items()}, berubah
