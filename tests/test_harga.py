# Aturan harga dan info kurang dari admin Pelita; semua angka tarif dari data/referensi/tarif.csv.
from cargo_extract.harga import estimasi_harga
from cargo_extract.pertanyaan import buat_balasan
from cargo_extract.schemas import EkstraksiLLM, InfoKurang
from cargo_extract.validator import normalisasi


def pesanan(**kolom):
    dasar = {"jenis_barang": "barang", "kategori_barang": None, "branded": None, "grup_koli": [],
             "berat_total": None, "cbm_disebut": None, "kota_tujuan": None, "jalur": None,
             "bahasa_pelanggan": "id", "catatan_ambigu": []}
    return normalisasi(EkstraksiLLM.model_validate(dasar | kolom))


def kg(n):
    return {"nilai": n, "satuan": "kg"}


def ukuran(p, l, t, koli=None):
    return [{"dimensi_per_koli": {"p": p, "l": l, "t": t, "satuan": "cm"}, "jumlah_koli": koli, "berat_per_koli": None}]


def test_udara_cukup_berat_tanpa_tanya_koli_atau_ukuran():
    p = pesanan(jenis_barang="tas", branded=True, berat_total=kg(10), kota_tujuan="Bandung", jalur="udara")
    assert p.info_kurang == []
    [e] = estimasi_harga(p)
    assert (e.golongan, e.total) == ("branded", 2_300_000)
    balasan = buat_balasan(p, [e])
    assert "10 kg × Rp230.000 = Rp2.300.000" in balasan
    assert "Jakarta ke Bandung lewat ekspedisi lokal" in balasan


def test_berat_volume_udara_selisih_setengah_tarif():
    p = pesanan(branded=False, berat_total=kg(10), grup_koli=ukuran(60, 50, 40), jalur="udara", kota_tujuan="Medan")
    [e] = estimasi_harga(p)
    assert (e.selisih_volume_kg, e.total) == (10, 10 * 220_000 + 10 * 110_000)   # 60x50x40/6000 = 20 kg


def test_laut_ukuran_tanpa_koli_dianggap_satu_dan_minimum():
    p = pesanan(jenis_barang="sepatu", grup_koli=ukuran(50, 40, 30), jalur="laut", kota_tujuan="Surabaya")
    assert InfoKurang.JUMLAH_KOLI not in p.info_kurang and p.info_kurang == []
    [e] = estimasi_harga(p)
    assert (e.golongan, e.jumlah, e.total) == ("umum", 0.1, 650_000)               # 0,06 CBM -> minimum 0,1
    assert any("dianggap 1 koli" in c for c in e.catatan)


def test_jakarta_minimal_satu_cbm_antar_gratis():
    p = pesanan(jenis_barang="baju", cbm_disebut=2, jalur="laut", kota_tujuan="Jakarta Barat")
    assert "Sudah termasuk antar ke alamat di Jakarta" in buat_balasan(p, estimasi_harga(p))


def test_jalur_belum_disebut_tampil_semua_pilihan_dan_tanya_jalur():
    p = pesanan(jenis_barang="sepatu", berat_total=kg(12), grup_koli=ukuran(50, 40, 30), kota_tujuan="Surabaya")
    assert p.info_kurang == [InfoKurang.JALUR]
    assert [(e.jalur.value, e.golongan) for e in estimasi_harga(p)] == [
        ("laut", "umum"), ("udara", "branded"), ("udara", "non_branded")]


def test_info_kurang_mengikuti_jalur():
    assert pesanan(jalur="laut", kota_tujuan="Medan").info_kurang == [InfoKurang.DIMENSI_ATAU_CBM]
    assert pesanan(jalur="udara", kota_tujuan="Medan", branded=False).info_kurang == [InfoKurang.BERAT]
    assert pesanan(kota_tujuan="Medan", berat_total=kg(5)).info_kurang == [InfoKurang.JALUR]
