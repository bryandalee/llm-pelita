# Semua isi chat di sini palsu.
from datetime import datetime

from cargo_extract.whatsapp import baca_ekspor, baca_teks, pengirim, potong_episode, tebak_admin

CONTOH_IPHONE = """Messages and calls are end-to-end encrypted. No one outside of this chat, not even WhatsApp, can read or listen to them.
[9/7/26, 4:43:45 PM] Toko Maju: Halo
[9/7/26, 4:43:46 PM] You: Halo kak
ada yang bisa dibantu?
[9/8/26, 10:35:22 AM] Toko Maju: 65 × 45 × 50 cm brp?
[9/8/26, 10:35:32 AM] Toko Maju: <image omitted>
[10/12/26, 10:28:57 AM] Toko Maju: Halo lagi
"""

CONTOH_ANDROID = """24/10/26 23.26 - Pesan dan panggilan terenkripsi secara end-to-end.
24/10/26 23.26 - Budi: mau kirim 3 dus
25/10/26 08.01 - Admin Pelita: IMG-20261025-WA0001.jpg (file terlampir)
siap kak
"""


def tulis(tmp_path, isi):
    path = tmp_path / "ekspor_uji" / "chat.txt"
    path.parent.mkdir()
    path.write_text(isi, encoding="utf-8")
    return path


def test_iphone(tmp_path):
    hasil = baca_ekspor(tulis(tmp_path, CONTOH_IPHONE))
    p = hasil.pesan
    assert len(p) == 5
    assert hasil.nama_pelanggan == {"Toko Maju"}
    assert p[0].waktu == datetime(2026, 9, 7, 16, 43, 45)
    assert (p[1].pengirim, p[1].teks) == ("admin", "Halo kak\nada yang bisa dibantu?")
    assert p[3].teks == "[foto]"
    assert p[3].lampiran[0].jenis == "foto" and p[3].lampiran[0].file is None


def test_android(tmp_path):
    p = baca_ekspor(tulis(tmp_path, CONTOH_ANDROID), {"Admin Pelita"}).pesan
    assert len(p) == 2
    assert p[0].waktu == datetime(2026, 10, 24, 23, 26)
    assert (p[1].pengirim, p[1].teks) == ("admin", "[foto]\nsiap kak")
    assert p[1].lampiran[0].file == "ekspor_uji/IMG-20261025-WA0001.jpg"


def test_pesan_sistem_dan_penanda_edit_dibuang(tmp_path):
    isi = ("[15/10/26, 20.06.00] Toko Maju: Toko Maju is a contact.\n"
           "[15/10/26, 20.07.00] Pelita Cargo: total 975.000 <This message was edited>\n")
    p = baca_ekspor(tulis(tmp_path, isi), {"Pelita Cargo"}).pesan
    assert [(x.pengirim, x.teks) for x in p] == [("admin", "total 975.000")]
    assert p[0].waktu == datetime(2026, 10, 15, 20, 7)


def test_potong_episode_setelah_jeda_seminggu(tmp_path):
    episode = potong_episode(baca_ekspor(tulis(tmp_path, CONTOH_IPHONE)).pesan)
    assert [len(e) for e in episode] == [4, 1]


# Format saat beberapa pesan disalin dari WhatsApp Desktop/Web (jam dulu, lalu tanggal).
CONTOH_SALINAN = """[09:15, 20/10/2026] Toko Maju: halo kak mau kirim sepatu
3 dus 60x40x40
[09:15, 20/10/2026] Toko Maju: Photo
ini barangnya
[09:20, 20/10/2026] Pelita Cargo: Halo, terima kasih telah menghubungi Pelita Cargo. Mohon isi form.
[13:05, 21/10/2026] Toko Maju: ke surabaya ya
"""


def test_salinan_desktop_dipisah_otomatis():
    hasil = baca_teks(CONTOH_SALINAN, nama_admin={"Pelita Cargo"})
    assert [p.pengirim for p in hasil.pesan] == ["pelanggan", "pelanggan", "admin", "pelanggan"]
    assert hasil.pesan[0].teks == "halo kak mau kirim sepatu\n3 dus 60x40x40"
    assert hasil.pesan[1].teks == "[foto]\nini barangnya"
    assert hasil.pesan[1].lampiran[0].jenis == "foto" and hasil.pesan[1].lampiran[0].file is None
    assert hasil.pesan[3].waktu == datetime(2026, 10, 21, 13, 5)


def test_pengirim_dan_tebak_admin_dari_template():
    assert pengirim(CONTOH_SALINAN) == ["Toko Maju", "Pelita Cargo"]
    assert tebak_admin(CONTOH_SALINAN, ("terima kasih telah menghubungi pelita cargo",)) == {"Pelita Cargo"}
    assert tebak_admin(CONTOH_SALINAN) == set()
