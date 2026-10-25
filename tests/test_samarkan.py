# Semua nama, alamat, dan nomor di sini palsu.
from cargo_extract.samarkan import samarkan_pesan
from cargo_extract.schemas import Pesan

PESAN = [
    Pesan(pengirim="pelanggan", teks="Halo, Andi!\n\nNama saya: Rina Wijaya\nRencana barang: botol 400ml"),
    Pesan(pengirim="admin", teks="FORMULIR\nNama Lengkap :\nAlamat Lengkap + Kode Pos : \nNo.HP :"),
    Pesan(pengirim="pelanggan", teks=(
        "Nama Lengkap : Rina Wijaya\nAlamat Lengkap + Kode Pos :\nJl Melati 3 No 7\n"
        "GUBENG, KOTA SURABAYA, ID 60281\nNo.HP : Rina (+62) 812-1111-2222")),
    Pesan(pengirim="admin", teks="Marking : TKO/RN/SEA\nNo.PL : F1234\nJmlh Koli : 2 Koli\nCbm / KG : 0.180 / 25 kg"),
    Pesan(pengirim="admin", teks="Tulis TKO-RN/ BY SEA di paket ya kak rina, hub 0812 3333 4444"),
]


def samarkan():
    hasil, pengganti = samarkan_pesan(PESAN, nama_kontak={"TKO-RN/ BY SEA"}, nama_tambahan=["Andi"])
    return [p.teks for p in hasil], pengganti


def test_data_pribadi_hilang():
    gabung = "\n".join(samarkan()[0]).casefold()
    for rahasia in ["andi", "rina", "wijaya", "melati", "60281", "1111-2222", "3333", "f1234", "tko"]:
        assert rahasia not in gabung


def test_info_barang_dan_kota_tetap():
    gabung = "\n".join(samarkan()[0])
    for tetap in ["botol 400ml", "KOTA SURABAYA", "2 Koli", "0.180 / 25 kg", "/SEA", "No.HP :"]:
        assert tetap in gabung


def test_formulir_kosong_tidak_dianggap_nama():
    teks, pengganti = samarkan()
    assert teks[1] == PESAN[1].teks
    assert "alamat" not in pengganti


def test_nomor_tanpa_kode_negara_wechat_marga_dan_desa():
    pesan = [
        Pesan(pengirim="admin", teks="送货前联系\n13912345678 王先生(海运）\n（微信 : contoh_id01)\nTransfer ke BCA 1234567890"),
        Pesan(pengirim="pelanggan", teks="Desa Sukamaju II\nKec.Sukamaju, Kabupaten Minahasa Selatan\nharga 1.030.000, 0.18 cbm"),
    ]
    teks = "\n".join(p.teks for p in samarkan_pesan(pesan, nama_kontak=set())[0])
    for rahasia in ["13912345678", "1234567890", "contoh_id01", "王先生", "Sukamaju II"]:
        assert rahasia not in teks
    for tetap in ["某先生", "微信 : [WECHAT1]", "Kabupaten Minahasa Selatan", "1.030.000", "0.18 cbm"]:
        assert tetap in teks


def test_kata_jalan_sebagai_kata_kerja_tidak_disamarkan():
    pesan = [
        Pesan(pengirim="admin", teks="tidak apa2 kak, bisa jalan tapi ikut harga minimum\n7,5 jt / cbm\n"
                                     "PS5 tanpa baterai bisa jalan BY AIR"),
        Pesan(pengirim="pelanggan", teks="kirim ke Jalan Sudirman 10 ya"),
        Pesan(pengirim="pelanggan", teks="Alamat:\njalan melati no 5\nKota Medan"),
    ]
    teks = [p.teks for p in samarkan_pesan(pesan, nama_kontak=set())[0]]
    assert teks[0] == pesan[0].teks
    assert teks[1] == "[ALAMAT JALAN]"
    assert teks[2] == "Alamat:\n[ALAMAT JALAN]\nKota Medan"


def test_kode_pos_yang_disebut_di_luar_blok_alamat():
    pesan = [Pesan(pengirim="pelanggan", teks="Saya di Kota Malang,\nKec Klojen, kode pos 65111\nongkir 12500 ya")]
    teks = samarkan_pesan(pesan, nama_kontak=set())[0][0].teks
    assert "65111" not in teks and "kode pos [KODEPOS]" in teks
    assert "12500" in teks                      # angka 5 digit lain (harga) tidak disentuh


def test_pengganti_konsisten():
    teks, pengganti = samarkan()
    rina = pengganti["rina"]
    assert rina in teks[2] and rina in teks[4]
    assert teks[3].startswith(f"Marking : {pengganti['tko-rn/ by sea']}/SEA")
