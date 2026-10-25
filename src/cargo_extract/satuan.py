"""Konversi satuan ke kg dan cm. Murni Python, tanpa LLM."""
from __future__ import annotations

from .schemas import SatuanBerat, SatuanPanjang

KE_KG = {
    SatuanBerat.KG: 1.0,
    SatuanBerat.GRAM: 0.001,
    SatuanBerat.JIN: 0.5,
    SatuanBerat.TON: 1000.0,
    SatuanBerat.LB: 0.45359237,
}

KE_CM = {
    SatuanPanjang.CM: 1.0,
    SatuanPanjang.MM: 0.1,
    SatuanPanjang.M: 100.0,
    SatuanPanjang.INCH: 2.54,
}


def ke_kg(nilai: float, satuan: SatuanBerat) -> float:
    return nilai * KE_KG[satuan]


def ke_cm(nilai: float, satuan: SatuanPanjang) -> float:
    return nilai * KE_CM[satuan]


def cbm(jumlah_koli: int, p_cm: float, l_cm: float, t_cm: float) -> float:
    """Volume total dalam m3."""
    return jumlah_koli * p_cm * l_cm * t_cm / 1_000_000
