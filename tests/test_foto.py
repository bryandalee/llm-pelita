# Gambar dibuat di tes (bukan foto asli); model diganti fungsi palsu supaya tes tidak butuh Ollama.
from PIL import Image

from cargo_extract import foto
from cargo_extract.schemas import Lampiran, Pesan


def gambar(tmp_path, nama="a.jpg", ukuran=(2000, 1000)):
    path = tmp_path / nama
    Image.new("RGB", ukuran, "white").save(path)
    return path


def test_perkecil_sisi_terpanjang(tmp_path):
    import io
    data = foto.perkecil(gambar(tmp_path), sisi=768)
    assert Image.open(io.BytesIO(data)).size == (768, 384)


def test_sisipkan_foto_hanya_pelanggan_dan_file_yang_ada(tmp_path, monkeypatch):
    gambar(tmp_path, "ada.jpg")
    monkeypatch.setattr(foto, "baca_foto", lambda path, **opsi: f"barang {path.stem}")
    pesan = [
        Pesan(pengirim="pelanggan", teks="ini kak [foto]", lampiran=[Lampiran(jenis="foto", file="ada.jpg")]),
        Pesan(pengirim="pelanggan", teks="[foto]", lampiran=[Lampiran(jenis="foto", file=None)]),     # Windows
        Pesan(pengirim="pelanggan", teks="[foto]", lampiran=[Lampiran(jenis="foto", file="hilang.jpg")]),
        Pesan(pengirim="admin", teks="[foto] cara kirim", lampiran=[Lampiran(jenis="foto", file="ada.jpg")]),
        Pesan(pengirim="pelanggan", teks="sepatu", lampiran=[Lampiran(jenis="foto", file="ada.jpg")]),
    ]
    teks = [p.teks for p in foto.sisipkan_foto(pesan, folder=tmp_path)]
    assert teks == ["ini kak [foto: barang ada]", "[foto]", "[foto]", "[foto] cara kirim",
                    "sepatu\n[foto: barang ada]"]


def test_jenis_dari_foto_hanya_jika_ekstraksi_kosong():
    from cargo_extract.schemas import EkstraksiLLM
    pesan = [Pesan(pengirim="pelanggan", teks="[foto: bukan foto barang]\nini kak [foto: tiang serat karbon]"),
             Pesan(pengirim="admin", teks="[foto: gudang kami]")]
    kosong = EkstraksiLLM.model_validate({
        "jenis_barang": None, "kategori_barang": None, "branded": None, "grup_koli": [], "berat_total": None,
        "cbm_disebut": None, "kota_tujuan": None, "jalur": None, "bahasa_pelanggan": "id", "catatan_ambigu": []})
    assert foto.lengkapi_jenis(kosong, pesan).jenis_barang == "tiang serat karbon"
    ada = kosong.model_copy(update={"jenis_barang": "sepatu"})
    assert foto.lengkapi_jenis(ada, pesan).jenis_barang == "sepatu"
    assert foto.jenis_dari_foto(pesan[1:]) is None
