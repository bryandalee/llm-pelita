from cargo_extract.schemas import EkstraksiLLM, InfoKurang, KodePeringatan
from cargo_extract.validator import normalisasi


def raw(**kolom):
    dasar = {
        "jenis_barang": "barang", "kategori_barang": None, "branded": None, "grup_koli": [],
        "berat_total": None, "cbm_disebut": None, "kota_tujuan": None, "jalur": None,
        "bahasa_pelanggan": "id", "catatan_ambigu": [],
    }
    return EkstraksiLLM.model_validate(dasar | kolom)


def grup(jumlah, p=None, l=None, t=None, satuan_dimensi=None, berat=None, satuan_berat="kg"):
    return {
        "jumlah_koli": jumlah,
        "dimensi_per_koli": {"p": p, "l": l, "t": t, "satuan": satuan_dimensi} if p else None,
        "berat_per_koli": {"nilai": berat, "satuan": satuan_berat} if berat else None,
    }


def kode(pesanan):
    return {p.kode for p in pesanan.peringatan}


def test_berat_per_koli_dan_satuan_diasumsikan():
    # sint_001: 4 ctn, 每箱 60*40*35, 15公斤
    p = normalisasi(raw(jenis_barang="Baju anak", kategori_barang="garmen", grup_koli=[grup(4, 60, 40, 35, berat=15)]))
    assert (p.jumlah_koli, p.berat_kg, p.cbm, p.cbm_sumber) == (4, 60, 0.336, "dihitung")
    assert p.jenis_barang == "baju anak"
    assert kode(p) == {KodePeringatan.SATUAN_DIASUMSIKAN}
    assert set(p.info_kurang) == {InfoKurang.KOTA_TUJUAN, InfoKurang.JALUR}


def test_jin_dan_cbm_disebut_yang_cocok():
    # sint_002: 5件 50*50*40, 总重 160斤, 0.5方
    p = normalisasi(raw(grup_koli=[grup(5, 50, 50, 40)], berat_total={"nilai": 160, "satuan": "jin"},
                        cbm_disebut=0.5, kota_tujuan="泗水"))
    assert (p.berat_kg, p.cbm, p.kota_tujuan) == (80, 0.5, "Surabaya")
    assert KodePeringatan.CBM_TIDAK_COCOK not in kode(p)


def test_meter_dan_alias_kota():
    # sint_004: 2 dus 0.6 x 0.4 x 0.4 m, totalnya 35 kilo, ke jakbar, via laut
    p = normalisasi(raw(grup_koli=[grup(2, 0.6, 0.4, 0.4, "m")], berat_total={"nilai": 35, "satuan": "kg"},
                        kota_tujuan="jakbar", jalur="laut", jenis_barang="mainan"))
    assert p.grup_koli[0].dimensi_cm == (60, 40, 40)
    assert (p.cbm, p.kota_tujuan, p.info_kurang, p.peringatan) == (0.192, "Jakarta Barat", [], [])


def test_udara_tanpa_branded_ditanyakan():
    p = normalisasi(raw(grup_koli=[grup(4, 45, 35, 30, "cm", 12)], kota_tujuan="Jakarta", jalur="udara"))
    assert p.info_kurang == [InfoKurang.BRANDED]


def test_hanya_cbm_disebut_tanpa_dimensi():
    p = normalisasi(raw(grup_koli=[grup(3)], cbm_disebut=1.2, berat_total={"nilai": 150, "satuan": "kg"}))
    assert (p.cbm, p.cbm_sumber) == (1.2, "disebut")
    assert InfoKurang.DIMENSI_ATAU_CBM not in p.info_kurang


def test_berat_total_tidak_konsisten():
    p = normalisasi(raw(grup_koli=[grup(4, 60, 40, 35, "cm", 15)], berat_total={"nilai": 100, "satuan": "kg"}))
    assert p.berat_kg == 100
    assert KodePeringatan.BERAT_TIDAK_KONSISTEN in kode(p)


def test_cbm_disebut_tidak_cocok():
    p = normalisasi(raw(grup_koli=[grup(4, 60, 40, 35, "cm")], cbm_disebut=1.0))
    assert p.cbm == 0.336
    assert KodePeringatan.CBM_TIDAK_COCOK in kode(p)


def test_mm_terbaca_cm_memicu_peringatan():
    p = normalisasi(raw(grup_koli=[grup(4, 600, 400, 350, "cm", 15)]))
    assert {KodePeringatan.DIMENSI_TIDAK_WAJAR, KodePeringatan.DENSITAS_JANGGAL} <= kode(p)


def test_di_bawah_minimum_laut():
    p = normalisasi(raw(grup_koli=[grup(1, 30, 30, 30, "cm", 5)], jalur="laut"))
    assert KodePeringatan.DI_BAWAH_MINIMUM in kode(p)


def test_kota_tidak_dikenal_tetap_disimpan():
    p = normalisasi(raw(kota_tujuan="Atlantis"))
    assert p.kota_tujuan == "Atlantis"
    assert KodePeringatan.KOTA_TIDAK_DIKENAL in kode(p)


def test_grup_yang_semuanya_kosong_dibuang():
    p = normalisasi(raw(grup_koli=[grup(None)], cbm_disebut=0.1))
    assert p.grup_koli == []
    assert (p.cbm, p.cbm_sumber) == (0.1, "disebut")


def test_kategori_dari_daftar_admin_mengalahkan_tebakan_model():
    p = normalisasi(raw(jenis_barang="Sandal jepit", kategori_barang="lartas_ringan"))
    assert p.kategori_barang == "umum"
    assert KodePeringatan.KATEGORI_PERLU_DICEK not in kode(p)
    # kata terpanjang menang; batas kata ("aki" tidak cocok di "kaki")
    assert normalisasi(raw(jenis_barang="kaos kaki")).kategori_barang == "semi_garmen"
    assert normalisasi(raw(jenis_barang="tas kain")).kategori_barang == "semi_garmen"
    assert normalisasi(raw(jenis_barang="aki motor")).kategori_barang == "lartas_berat"


def test_barang_di_luar_daftar_pakai_tebakan_model_dan_ditandai():
    p = normalisasi(raw(jenis_barang="jam dinding", kategori_barang="umum"))
    assert p.kategori_barang == "umum"
    assert KodePeringatan.KATEGORI_PERLU_DICEK in kode(p)
    assert KodePeringatan.KATEGORI_PERLU_DICEK not in kode(normalisasi(raw(jenis_barang=None)))


def test_chat_kosong_semua_kurang():
    p = normalisasi(raw(jenis_barang=None))
    assert set(p.info_kurang) == {
        InfoKurang.JENIS_BARANG, InfoKurang.JUMLAH_KOLI, InfoKurang.BERAT,
        InfoKurang.DIMENSI_ATAU_CBM, InfoKurang.KOTA_TUJUAN, InfoKurang.JALUR,
    }
