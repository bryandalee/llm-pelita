import pytest

from cargo_extract.satuan import cbm, ke_cm, ke_kg
from cargo_extract.schemas import SatuanBerat, SatuanPanjang


def test_jin_ke_kg():
    assert ke_kg(160, SatuanBerat.JIN) == 80


def test_meter_ke_cm():
    assert ke_cm(0.6, SatuanPanjang.M) == pytest.approx(60)


def test_cbm():
    assert cbm(4, 60, 40, 35) == pytest.approx(0.336)
