# Semua isi chat di sini palsu.
from pathlib import Path

from streamlit.testing.v1 import AppTest

from cargo_extract import config, extractor
from cargo_extract.dataset import muat_chats
from cargo_extract.label import (
    bangun_dataset,
    file_dataset,
    file_draft_label,
    file_split,
    info_kurang_dari_label,
    muat_label,
    simpan_label,
)
from cargo_extract.schemas import DraftChat, EkstraksiLLM, LabelManual, LabelPesanan, Pesan, TandaEpisode
from cargo_extract.tanda import simpan_tanda

DEV = Path(__file__).resolve().parents[1] / "data" / "chats" / "dev.jsonl"


def test_aturan_info_kurang_sama_dengan_label_dev():
    for c in muat_chats(DEV):
        assert set(info_kurang_dari_label(c.label)) == set(c.label.info_kurang), c.id


def siapkan(tmp_path, monkeypatch, potong=2):
    monkeypatch.setattr(config, "PRIVAT_DIR", tmp_path)
    pesan = [Pesan(pengirim="pelanggan", teks="mau kirim baju 2 dus 50x40x30 cm total 20kg ke jakbar via laut"),
             Pesan(pengirim="admin", teks="Pagi kak"),
             Pesan(pengirim="admin", teks="VIA LAUT\nGarmen\n10.3 jt / cbm")]
    draft = DraftChat(id="uji_ep01", sumber="uji", episode=1, pesan=pesan)
    (tmp_path / "uji.jsonl").write_text(draft.model_dump_json() + "\n", encoding="utf-8")
    simpan_tanda("uji_ep01", TandaEpisode(jenis="permintaan_harga", potong_sebelum=potong))


def test_bangun_dataset_dan_deteksi_potong_berubah(tmp_path, monkeypatch):
    siapkan(tmp_path, monkeypatch)
    simpan_label("uji_ep01", LabelManual(label=LabelPesanan(jenis_barang="baju"), bahasa=["id"], potong_sebelum=2))
    assert bangun_dataset() == ({"dev": 0, "test": 1}, [])     # belum tercantum di split.json -> test
    [contoh] = muat_chats(file_dataset("test"))
    assert len(contoh.pesan) == 2 and contoh.meta.sumber == "disamarkan"

    simpan_tanda("uji_ep01", TandaEpisode(jenis="permintaan_harga", potong_sebelum=1))
    assert bangun_dataset() == ({"dev": 0, "test": 1}, ["uji_ep01"])


def test_episode_di_split_json_masuk_dev(tmp_path, monkeypatch):
    siapkan(tmp_path, monkeypatch)
    file_split().write_text('{"dev": ["uji_ep01"]}', encoding="utf-8")
    simpan_label("uji_ep01", LabelManual(label=LabelPesanan(jenis_barang="baju"), bahasa=["id"], potong_sebelum=2))
    assert bangun_dataset()[0] == {"dev": 1, "test": 0}
    assert muat_chats(file_dataset("test")) == []


def test_draft_label_jadi_isian_awal_tapi_belum_tersimpan(tmp_path, monkeypatch):
    siapkan(tmp_path, monkeypatch)
    monkeypatch.setattr(extractor, "dari_cache", lambda *a, **kw: None)
    simpan_label("uji_ep01", LabelManual(label=LabelPesanan(jenis_barang="baju anak"), bahasa=["id"],
                                         tag=["formulir"], potong_sebelum=2), file_draft_label())

    at = AppTest.from_file("../app/label.py").run(timeout=30)
    assert not at.exception
    assert at.text_input(key="jenis_uji_ep01").value == "baju anak"
    assert at.multiselect(key="tag_uji_ep01").value == ["formulir"]
    assert muat_label() == {}                      # belum diverifikasi = belum masuk label.json


def test_halaman_label(tmp_path, monkeypatch):
    siapkan(tmp_path, monkeypatch)
    draft_model = EkstraksiLLM.model_validate({
        "jenis_barang": "Baju", "kategori_barang": None, "branded": None,
        "grup_koli": [{"dimensi_per_koli": {"p": 50, "l": 40, "t": 30, "satuan": "cm"},
                       "jumlah_koli": 2, "berat_per_koli": None}],
        "berat_total": {"nilai": 20, "satuan": "kg"}, "cbm_disebut": None, "kota_tujuan": "jakbar",
        "jalur": "laut", "bahasa_pelanggan": "id", "catatan_ambigu": [],
    })
    monkeypatch.setattr(extractor, "dari_cache", lambda *a, **kw: draft_model)

    at = AppTest.from_file("../app/label.py").run(timeout=30)
    assert not at.exception
    assert at.text_input(key="jenis_uji_ep01").value == "baju"
    assert at.selectbox(key="kota_uji_ep01").value == "Jakarta Barat"
    at.button(key="simpan_uji_ep01").click().run(timeout=30)
    assert not at.exception

    lab = muat_label()["uji_ep01"].label
    assert (lab.jumlah_koli, lab.berat_kg, lab.cbm, lab.kota_tujuan) == (2, 20, 0.12, "Jakarta Barat")
    assert lab.info_kurang == []
    assert len(muat_chats(file_dataset("test"))) == 1

    # Angka yang sudah terisi harus bisa dikosongkan lagi.
    at.text_input(key="berat_uji_ep01").set_value("").run(timeout=30)
    at.button(key="simpan_uji_ep01").click().run(timeout=30)
    lab = muat_label()["uji_ep01"].label
    assert lab.berat_kg is None and "berat" not in lab.info_kurang     # laut: cukup ukuran/CBM
