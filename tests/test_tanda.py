# Semua isi chat di sini palsu.
from streamlit.testing.v1 import AppTest

from cargo_extract import config
from cargo_extract.schemas import DraftChat, Pesan, TandaEpisode
from cargo_extract.tanda import (
    input_episode,
    jawaban_harga_khusus,
    muat_tanda,
    saran_titik_potong,
    simpan_tanda,
)

PRICELIST = "VIA UDARA\nBranded - 230rb/kg\nnon-Branded - 220rb/kg\nVIA LAUT\nTas 6 jt / cbm\nUmum 6,5 jt / cbm"


def pesan(*isi):
    return [Pesan(pengirim=pengirim, teks=teks) for pengirim, teks in isi]


def test_pricelist_umum_bukan_titik_potong():
    p = pesan(("pelanggan", "mau tanya ongkir"), ("admin", PRICELIST), ("pelanggan", "60x40x40 brp?"),
              ("admin", "VIA LAUT\nUmum\n6,5 jt / cbm"), ("pelanggan", "ke jakbar"))
    assert saran_titik_potong(p) == 3


def test_template_jasa_order_bukan_titik_potong():
    jasa_order = ("Kami juga menyediakan layanan *Jasa Order*. Rincian ketentuan biaya admin (charge):\n"
                  "Total Belanja < Rp 2.000.000: Charge Rp 150.000")
    p = pesan(("pelanggan", "mau order mesin"), ("admin", jasa_order), ("admin", "mesin 2 cbm x 7 jt = 14 jt"))
    assert saran_titik_potong(p) == 2


def test_jenis_pesan_harga():
    # Pricelist yang sudah dipersempit ke tarif barang pelanggan = jawaban khusus.
    assert jawaban_harga_khusus("VIA UDARA\nBranded - 230rb/kg\nnon-Branded - 220rb/kg\nVIA LAUT\n10.3 jt / cbm")
    assert jawaban_harga_khusus("di 1.030.000 kak untuk baju")
    assert jawaban_harga_khusus("Terkena biaya ongkir sekitar 89 rb kak")
    # Daftar umum.
    assert not jawaban_harga_khusus(PRICELIST)
    assert not jawaban_harga_khusus("VIA UDARA (min. 3kg)\nBranded - 230rb/kg\nnon-Branded - 220rb/kg")
    assert not jawaban_harga_khusus("VIA LAUT, Dihitung berdasarkan CBM/Kubik. 1CBM = 100x100x100cm")


def test_hitungan_cbm_jadi_titik_potong():
    p = pesan(("pelanggan", "60x40x40 brp?"), ("admin", "60x40x40 = 0.096 cbm"))
    assert saran_titik_potong(p) == 1


def test_tanpa_jawaban_harga():
    p = pesan(("pelanggan", "barang sudah dikirim ya"), ("admin", "Cbm / KG : 0.180 / 25 kg"))
    assert saran_titik_potong(p) is None


def test_simpan_dan_potong(tmp_path):
    draft = DraftChat(id="uji_ep01", sumber="uji", episode=1, pesan=pesan(("pelanggan", "a"), ("admin", "b")))
    simpan_tanda("uji_ep01", TandaEpisode(jenis="permintaan_harga", potong_sebelum=1), tmp_path / "tanda.json")
    tanda = muat_tanda(tmp_path / "tanda.json")
    assert [p.teks for p in input_episode(draft, tanda["uji_ep01"])] == ["a"]
    assert input_episode(draft, None) == draft.pesan


def test_halaman_tandai(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRIVAT_DIR", tmp_path)
    draft = DraftChat(id="uji_ep01", sumber="uji", episode=1, pesan=pesan(
        ("pelanggan", "60x40x40 brp?"), ("admin", "0.096 cbm x 6.500.000 = 624.000"), ("pelanggan", "ke jakbar")))
    (tmp_path / "uji.jsonl").write_text(draft.model_dump_json() + "\n", encoding="utf-8")

    at = AppTest.from_file("../app/tandai.py").run()
    assert not at.exception
    assert at.selectbox(key="potong_uji_ep01").value == 1          # saran otomatis
    at.button(key="simpan_uji_ep01").click().run()
    assert not at.exception
    assert muat_tanda(tmp_path / "tanda.json")["uji_ep01"] == TandaEpisode(jenis="permintaan_harga", potong_sebelum=1)
