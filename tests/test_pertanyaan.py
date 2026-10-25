# Semua isi chat di sini palsu.
from streamlit.testing.v1 import AppTest

from pathlib import Path

from cargo_extract import extractor
from cargo_extract.dataset import muat_chats, parse_teks_chat, teks_chat
from cargo_extract.pertanyaan import bahasa_balasan, buat_pertanyaan
from cargo_extract.schemas import EkstraksiLLM, GrupKoli, InfoKurang, Pesanan

DEV = Path(__file__).resolve().parents[1] / "data" / "chats" / "dev.jsonl"


def test_satu_ukuran_tanpa_koli_jadi_konfirmasi():
    p = Pesanan(bahasa_pelanggan="id", grup_koli=[GrupKoli(dimensi_cm=(65, 45, 50))],
                info_kurang=[InfoKurang.JUMLAH_KOLI, InfoKurang.KOTA_TUJUAN])
    assert buat_pertanyaan(p) == ("Baik kak, untuk menghitung ongkirnya boleh dibantu info berikut:\n"
                                  "1. ukuran 65x45x50 cm itu untuk 1 koli ya kak?\n"
                                  "2. dikirim ke kota mana?")


def test_bahasa_mandarin_dan_lengkap():
    assert buat_pertanyaan(Pesanan(bahasa_pelanggan="zh", info_kurang=[InfoKurang.JALUR])).endswith("走海运还是空运？")
    assert buat_pertanyaan(Pesanan(bahasa_pelanggan="id")) is None


def test_bahasa_balasan_dari_pesan_pelanggan():
    chat = {c.id: c for c in muat_chats(DEV)}
    assert bahasa_balasan(chat["sint_001"].pesan) == "id"   # Indonesia + sedikit Mandarin
    assert bahasa_balasan(chat["sint_002"].pesan) == "zh"
    assert bahasa_balasan(chat["sint_003"].pesan) == "en"
    assert bahasa_balasan(chat["sint_004"].pesan) == "id"


def test_parse_teks_chat_kebalikan_teks_chat():
    teks = "pelanggan: halo\nadmin: Barang apa kak?\npelanggan: baju 2 dus\n60x40x40"
    pesan = parse_teks_chat(teks)
    assert [p.pengirim for p in pesan] == ["pelanggan", "admin", "pelanggan"]
    assert teks_chat(pesan) == teks
    assert parse_teks_chat("mau kirim sepatu")[0].pengirim == "pelanggan"


def test_halaman_demo(monkeypatch):
    raw = EkstraksiLLM.model_validate({
        "jenis_barang": "sepatu", "kategori_barang": "umum", "branded": None,
        "grup_koli": [{"dimensi_per_koli": {"p": 60, "l": 40, "t": 40, "satuan": "cm"}, "jumlah_koli": 3,
                       "berat_per_koli": None}],
        "berat_total": None, "cbm_disebut": None, "kota_tujuan": "sby", "jalur": None,
        "bahasa_pelanggan": "id", "catatan_ambigu": [],
    })
    monkeypatch.setattr(extractor, "ekstrak", lambda *a, **kw: raw)
    import cargo_extract.pipeline as pipeline
    monkeypatch.setattr(pipeline, "ekstrak", lambda *a, **kw: raw)

    at = AppTest.from_file("../app/streamlit_app.py").run(timeout=30)
    assert not at.exception
    at.text_area(key="chat").set_value("pelanggan: kak mau kirim sepatu 3 dus 60x40x40 ke sby").run(timeout=30)
    at.button[0].click().run(timeout=30)
    assert not at.exception
    teks_kode = " ".join(c.value for c in at.code)
    assert "berat totalnya" in teks_kode and "via laut atau udara" in teks_kode
