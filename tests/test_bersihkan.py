# Semua isi chat di sini palsu (teks template ditulis ulang secara ringkas).
from cargo_extract.bersihkan import buang_template
from cargo_extract.schemas import Pesan


def test_buang_template_admin_saja():
    pesan = [
        Pesan(pengirim="pelanggan", teks="Halo, mau tanya ongkir baju 2 dus"),
        Pesan(pengirim="admin", teks="Halo, terima kasih telah menghubungi Pelita Cargo. Mohon isi form."),
        Pesan(pengirim="admin", teks="Pagi kak, barangnya apa?"),
        Pesan(pengirim="admin", teks="Kami menyediakan 2 pilihan pengiriman:\nVIA LAUT ...\nVIA UDARA ..."),
        Pesan(pengirim="admin", teks="VIA UDARA\nBranded - 230rb/kg\nnon-Branded - 220rb/kg\nVIA LAUT\nTas 6 jt / cbm\nUmum 6,5 jt / cbm"),
        Pesan(pengirim="pelanggan", teks="Cara Kirim Barang ke Gudang Kami di China itu gimana kak?"),
        Pesan(pengirim="admin", teks="VIA LAUT\nGarmen\n10.3 jt / cbm"),
    ]
    sisa = [p.teks for p in buang_template(pesan)]
    assert sisa == [
        "Halo, mau tanya ongkir baju 2 dus",
        "Pagi kak, barangnya apa?",
        "Cara Kirim Barang ke Gudang Kami di China itu gimana kak?",   # pesan pelanggan tidak dibuang
        "VIA LAUT\nGarmen\n10.3 jt / cbm",                              # jawaban harga khusus tetap
    ]
