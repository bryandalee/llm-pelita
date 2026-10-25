import pytest
from pydantic import ValidationError

from cargo_extract.schemas import EkstraksiLLM, GrupKoliMentah, LabelPesanan, Pesan


def test_semua_kolom_llm_wajib():
    # Model harus mengisi setiap kolom secara eksplisit (null jika tidak ada).
    skema = EkstraksiLLM.model_json_schema()
    assert set(skema["required"]) == set(skema["properties"])


def test_dimensi_diisi_sebelum_jumlah_koli():
    # Lihat docstring GrupKoliMentah: urutan ini memengaruhi hasil model.
    kolom = list(GrupKoliMentah.model_json_schema()["properties"])
    assert kolom.index("dimensi_per_koli") < kolom.index("jumlah_koli")


def test_label_menolak_typo_kolom():
    with pytest.raises(ValidationError):
        LabelPesanan.model_validate({"kota_tujan": "Jakarta"})


def test_label_menolak_koli_nol():
    with pytest.raises(ValidationError):
        LabelPesanan.model_validate({"jumlah_koli": 0})


def test_pesan_tanpa_lampiran():
    assert Pesan(pengirim="pelanggan", teks="halo").lampiran == []
