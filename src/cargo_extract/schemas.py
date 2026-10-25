"""Skema data: output LLM (mentah), pesanan ternormalisasi, label, dan record dataset."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------- Kosakata bersama ----------

class SatuanBerat(str, Enum):
    KG = "kg"          # kg, kilo, kgs, 公斤, 千克
    GRAM = "g"
    JIN = "jin"        # 斤 = 0,5 kg
    TON = "ton"        # 吨
    LB = "lb"


class SatuanPanjang(str, Enum):
    CM = "cm"          # 厘米
    MM = "mm"
    M = "m"            # 米
    INCH = "inch"


class KategoriBarang(str, Enum):
    """Kategori tarif laut di pricelist. Tarif udara ditentukan `branded`."""
    TAS = "tas"
    UMUM = "umum"
    LARTAS_RINGAN = "lartas_ringan"
    LARTAS_BERAT = "lartas_berat"
    SEMI_GARMEN = "semi_garmen"
    GARMEN = "garmen"


class Jalur(str, Enum):
    LAUT = "laut"
    UDARA = "udara"


class Bahasa(str, Enum):
    ID = "id"
    ZH = "zh"
    EN = "en"


class InfoKurang(str, Enum):
    JENIS_BARANG = "jenis_barang"
    JUMLAH_KOLI = "jumlah_koli"
    BERAT = "berat"
    DIMENSI_ATAU_CBM = "dimensi_atau_cbm"   # cukup salah satu
    KOTA_TUJUAN = "kota_tujuan"
    JALUR = "jalur"
    BRANDED = "branded"                     # hanya untuk udara


class KodePeringatan(str, Enum):
    SATUAN_DIASUMSIKAN = "satuan_diasumsikan"        # "60x40x35" tanpa satuan -> cm
    CBM_TIDAK_COCOK = "cbm_tidak_cocok"              # CBM disebut vs dihitung beda > 10%
    BERAT_TIDAK_WAJAR = "berat_tidak_wajar"          # mis. > 200 kg per koli
    DIMENSI_TIDAK_WAJAR = "dimensi_tidak_wajar"      # sisi < 1 cm atau > 300 cm
    DENSITAS_JANGGAL = "densitas_janggal"            # kg/m3 di luar rentang -> curiga salah satuan
    BERAT_TIDAK_KONSISTEN = "berat_tidak_konsisten"  # total != per_koli x jumlah
    DI_BAWAH_MINIMUM = "di_bawah_minimum"            # laut < 0,1 CBM, udara < 3 kg
    KOTA_TIDAK_DIKENAL = "kota_tidak_dikenal"        # tidak ada di data/referensi/kota.csv


# ---------- Lapis 1: output LLM (apa yang DIKATAKAN, tanpa hitung/konversi) ----------
# Semua kolom wajib diisi (null jika tidak ada), supaya model menimbang setiap kolom.

class BeratMentah(BaseModel):
    nilai: float
    satuan: SatuanBerat | None = Field(description="Satuan seperti tertulis; null jika tidak disebut")


class DimensiMentah(BaseModel):
    p: float
    l: float
    t: float
    satuan: SatuanPanjang | None = Field(description="Satuan seperti tertulis; null jika tidak disebut")


class GrupKoliMentah(BaseModel):
    """Sekelompok koli berukuran sama, mis. '3 ctn 50x40x30 @12kg'.

    Urutan kolom disengaja: model mengisi JSON dari atas. Jika jumlah_koli di depan dan pelanggan
    tidak menyebut jumlah koli, model mengambil angka ukuran pertama sebagai jumlah koli
    ("65 × 45 × 50" -> 65 koli). Jadi dimensi diisi lebih dulu.
    """
    dimensi_per_koli: DimensiMentah | None
    jumlah_koli: int | None = Field(description="Jumlah koli/ctn/dus/件/箱, BUKAN jumlah pcs barang; null jika tidak disebut")
    berat_per_koli: BeratMentah | None = Field(description="Hanya jika disebut per koli (@, each, 每箱, 每件)")


class EkstraksiLLM(BaseModel):
    """Skema output model. Jika pelanggan merevisi, ambil nilai terakhir."""
    jenis_barang: str | None = Field(description="Nama barang singkat dalam bahasa Indonesia")
    kategori_barang: KategoriBarang | None = Field(description="Kategori tarif laut; null jika tidak yakin")
    branded: bool | None = Field(
        description="true jika disebut bermerek/branded/品牌; false jika disebut tanpa merek; null jika tidak disebut")
    grup_koli: list[GrupKoliMentah]
    berat_total: BeratMentah | None = Field(
        description="Berat seluruh kiriman jika DISEBUT (total, totalnya, 总重, 一共); jangan dihitung sendiri")
    cbm_disebut: float | None = Field(description="CBM/kubik/方 yang DISEBUT pelanggan, bukan hasil hitung")
    kota_tujuan: str | None = Field(description="Kota tujuan di Indonesia; nama baku jika yakin (泗水 -> Surabaya)")
    jalur: Jalur | None = Field(
        description="Hanya jika pelanggan menyebut laut/udara/sea/air/海运/空运; selain itu null")
    bahasa_pelanggan: Bahasa = Field(description="Bahasa dominan pelanggan, untuk bahasa pertanyaan balik")
    catatan_ambigu: list[str] = Field(description="Maksimal 2 catatan pendek tentang hal yang benar-benar tidak jelas")


# ---------- Lapis 2: pesanan ternormalisasi (dihasilkan kode, bukan LLM) ----------

class GrupKoli(BaseModel):
    model_config = ConfigDict(extra="forbid")
    jumlah_koli: int | None = Field(None, ge=1)
    dimensi_cm: tuple[float, float, float] | None = None   # (p, l, t)
    berat_per_koli_kg: float | None = Field(None, gt=0)


class LabelPesanan(BaseModel):
    """Kolom yang DINILAI. Format yang sama untuk label manual dan prediksi."""
    model_config = ConfigDict(extra="forbid")   # typo nama kolom di file label langsung error
    jenis_barang: str | None = None
    kategori_barang: KategoriBarang | None = None
    branded: bool | None = None
    jumlah_koli: int | None = Field(None, ge=1)          # total semua grup
    berat_kg: float | None = Field(None, gt=0)           # total, gross
    grup_koli: list[GrupKoli] = Field(default_factory=list)
    cbm: float | None = Field(None, gt=0)                # total
    kota_tujuan: str | None = None
    jalur: Jalur | None = None
    info_kurang: list[InfoKurang] = Field(default_factory=list)


class Peringatan(BaseModel):
    kode: KodePeringatan
    pesan: str


class Pesanan(LabelPesanan):
    """Output akhir pipeline = kolom label + hal yang tidak dinilai otomatis."""
    cbm_sumber: Literal["dihitung", "disebut"] | None = None
    bahasa_pelanggan: Bahasa
    peringatan: list[Peringatan] = Field(default_factory=list)
    pertanyaan_balik: str | None = None


# ---------- Dataset ----------

class Lampiran(BaseModel):
    jenis: Literal["foto", "pdf", "excel", "lainnya"]
    file: str | None = None   # path relatif terhadap data/raw/; None jika media tidak ikut diekspor


class Pesan(BaseModel):
    pengirim: Literal["pelanggan", "admin"]
    teks: str
    lampiran: list[Lampiran] = Field(default_factory=list)
    waktu: datetime | None = None


class DraftChat(BaseModel):
    """Satu episode chat asli yang sudah disamarkan, belum berlabel (data/privat/, tidak di-commit)."""
    id: str
    sumber: str          # nama folder ekspor di data/raw/
    episode: int
    pesan: list[Pesan]


JenisEpisode = Literal["permintaan_harga", "tindak_lanjut", "lainnya"]


class TandaEpisode(BaseModel):
    """Keputusan manual per episode (docs/panduan_label.md, bagian 'Chat asli')."""
    model_config = ConfigDict(extra="forbid")
    jenis: JenisEpisode
    potong_sebelum: int | None = Field(None, ge=0)   # indeks pesan pertama yang TIDAK masuk input
    catatan: str = ""


class MetaChat(BaseModel):
    bahasa: list[Bahasa]
    sumber: Literal["sintetis", "disamarkan"]
    tag: list[str] = Field(default_factory=list)   # daftar tag: docs/panduan_label.md


class ContohChat(BaseModel):
    """Satu baris di data/chats/{dev,test}.jsonl."""
    model_config = ConfigDict(extra="forbid")
    id: str
    pesan: list[Pesan]
    label: LabelPesanan
    meta: MetaChat


class LabelManual(BaseModel):
    """Label satu episode chat asli (data/privat/label.json), dibuat di app/label.py."""
    model_config = ConfigDict(extra="forbid")
    label: LabelPesanan
    bahasa: list[Bahasa]
    tag: list[str] = Field(default_factory=list)
    potong_sebelum: int | None   # titik potong saat dilabel; jika tanda berubah, label perlu dicek ulang
