from cargo_extract.schemas import ContohChat, GrupKoli, Jalur, LabelPesanan, MetaChat
from evaluasi.bandingkan import berubah
from evaluasi.metrik import KOLOM, bandingkan_kolom, kolom_diabaikan, ringkas

LABEL = LabelPesanan.model_validate({
    "jenis_barang": "baju anak", "kategori_barang": "garmen", "jumlah_koli": 4, "berat_kg": 60,
    "grup_koli": [{"jumlah_koli": 4, "dimensi_cm": [60, 40, 35], "berat_per_koli_kg": 15}],
    "cbm": 0.336, "info_kurang": ["kota_tujuan", "jalur"],
})


def test_identik_semua_benar():
    assert set(bandingkan_kolom(LABEL, LABEL).values()) == {"benar"}


def test_jenis_status():
    pred = LABEL.model_copy(update={
        "jalur": Jalur.LAUT,                     # label null -> halusinasi
        "jumlah_koli": None,                     # label isi -> terlewat
        "berat_kg": 61,                          # beda 1,7% -> salah
        "cbm": 0.34,                             # beda 1,2% -> masih benar
        "grup_koli": [GrupKoli(jumlah_koli=4, dimensi_cm=(35, 60, 40))],  # urutan sisi beda -> benar
    })
    s = bandingkan_kolom(LABEL, pred)
    assert (s["jalur"], s["jumlah_koli"], s["berat_kg"], s["cbm"], s["grup_koli"]) == (
        "halusinasi", "terlewat", "salah", "benar", "benar")


def test_kolom_diabaikan_tidak_dihitung():
    pred = LABEL.model_copy(update={"kategori_barang": None})
    s = bandingkan_kolom(LABEL, pred, frozenset({"kategori_barang"}))
    assert s["kategori_barang"] == "diabaikan"
    m = ringkas([(LABEL, pred), (LABEL, LABEL)], [frozenset({"kategori_barang"}), frozenset()])
    assert m["per_kolom"]["kategori_barang"]["akurasi"] == 1.0
    assert m["chat_semua_benar"] == 2


def test_kategori_tidak_dinilai_jika_jenis_barang_kosong():
    contoh = ContohChat(id="c1", pesan=[], meta=MetaChat(bahasa=["id"], sumber="sintetis"),
                        label=LABEL.model_copy(update={"jenis_barang": None}))
    assert kolom_diabaikan(contoh) == {"kategori_barang", "branded"}
    assert kolom_diabaikan(contoh.model_copy(update={"label": LABEL})) == frozenset()


def test_berubah_antar_run():
    awal = {"c1": dict.fromkeys(KOLOM, "benar") | {"jalur": "halusinasi"}}
    akhir = {"c1": dict.fromkeys(KOLOM, "benar") | {"kota_tujuan": "salah"}}
    assert berubah(awal, akhir) == [("c1", "kota_tujuan", "memburuk"), ("c1", "jalur", "membaik")]


def test_ringkas_info_kurang():
    pred = LABEL.model_copy(update={"info_kurang": ["kota_tujuan"]})
    m = ringkas([(LABEL, LABEL), (LABEL, pred)])
    assert m["chat_semua_benar"] == 1
    assert m["per_kolom"]["info_kurang"]["akurasi"] == 0.5
    assert m["info_kurang"] == {"precision": 1.0, "recall": 0.75}
