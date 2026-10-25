"""Cek kewarasan file label: semua baris valid dan angkanya saling konsisten."""
import csv
from pathlib import Path

import pytest

from cargo_extract.dataset import muat_chats
from cargo_extract.satuan import cbm

DATA = Path(__file__).resolve().parents[1] / "data"
SPLITS = sorted((DATA / "chats").glob("*.jsonl"))
CHATS = [c for path in SPLITS for c in muat_chats(path)]
KOTA_BAKU = {row["nama_baku"] for row in csv.DictReader((DATA / "referensi" / "kota.csv").open(encoding="utf-8"))}


def test_ada_data():
    assert CHATS


def test_id_unik():
    ids = [c.id for c in CHATS]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("c", CHATS, ids=lambda c: c.id)
def test_label_konsisten(c):
    lab = c.label
    grup = lab.grup_koli
    if grup and all(g.jumlah_koli for g in grup):
        assert lab.jumlah_koli == sum(g.jumlah_koli for g in grup)
    if grup and all(g.jumlah_koli and g.dimensi_cm for g in grup):
        assert lab.cbm == pytest.approx(sum(cbm(g.jumlah_koli, *g.dimensi_cm) for g in grup), abs=0.0015)
    if grup and all(g.jumlah_koli and g.berat_per_koli_kg for g in grup):
        assert lab.berat_kg == pytest.approx(sum(g.jumlah_koli * g.berat_per_koli_kg for g in grup))
    if lab.kota_tujuan is not None:
        assert lab.kota_tujuan in KOTA_BAKU
