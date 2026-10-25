# Chat palsu; embedding diganti hitungan kata supaya tes tidak butuh Ollama.
from cargo_extract.extractor import _system_dan_kunci
from cargo_extract.riwayat import bangun_bank, cari, format_konteks, konteks_untuk, sumber
from cargo_extract.schemas import ContohChat, KategoriBarang, LabelPesanan, MetaChat, Pesan

KATA = ["tas", "baju", "sepatu", "aki"]


def embed_palsu(teks: list[str]) -> list[list[float]]:
    return [[float(t.lower().count(k)) for k in KATA] + [0.1] for t in teks]


def chat(id_, teks, **label) -> ContohChat:
    return ContohChat(id=id_, pesan=[Pesan(pengirim="pelanggan", teks=teks),
                                     Pesan(pengirim="admin", teks="baju tas sepatu aki")],
                      label=LabelPesanan(**label), meta=MetaChat(bahasa=["id"], sumber="disamarkan"))


BANK_CHAT = [
    chat("ekspor_01_ep01", "kirim tas wanita 3 dus", jenis_barang="tas wanita",
         kategori_barang=KategoriBarang.TAS, branded=False),
    chat("ekspor_02_ep01", "baju anak 5 karung", jenis_barang="baju anak",
         kategori_barang=KategoriBarang.GARMEN),
    chat("ekspor_03_ep01", "sepatu nike", jenis_barang="sepatu", branded=True),
    chat("ekspor_03_ep02", "tas lagi kak", jenis_barang="tas", kategori_barang=KategoriBarang.TAS),
    chat("ekspor_04_ep01", "tas 2 koli"),                                      # tanpa jenis barang
    chat("ekspor_05_ep01", "aki motor", jenis_barang="aki motor"),            # tanpa keputusan admin
]


def test_sumber_episode():
    assert sumber("ekspor_03_ep02") == "ekspor_03"
    assert sumber("sint_001") == "sint_001"


def test_bank_hanya_contoh_berguna_dan_teks_pelanggan_saja():
    bank = bangun_bank(BANK_CHAT, embed_palsu)
    assert [c.id for c in bank] == ["ekspor_01_ep01", "ekspor_02_ep01", "ekspor_03_ep01", "ekspor_03_ep02"]
    assert bank[1].vektor[:4] == [0, 1, 0, 0]          # pesan admin tidak ikut di-embed


def test_cari_urut_kemiripan_dan_buang_ekspor_sama():
    bank = bangun_bank(BANK_CHAT, embed_palsu)
    vektor = embed_palsu(["tas ransel"])[0]
    assert [c.id for c in cari(bank, vektor, k=2)] == ["ekspor_01_ep01", "ekspor_03_ep02"]
    assert [c.id for c in cari(bank, vektor, kecuali_sumber="ekspor_03", k=2)] == ["ekspor_01_ep01",
                                                                                   "ekspor_02_ep01"]
    assert len(cari(bank, vektor, kecuali_sumber="ekspor_03", k=0)) == 2       # k=0: semua sisa


def test_konteks_untuk_chat_sendiri_tidak_ikut():
    bank = bangun_bank(BANK_CHAT, embed_palsu)
    teks = konteks_untuk(BANK_CHAT[0].pesan, bank, kecuali_sumber="ekspor_01", fungsi_embed=embed_palsu, k=1)
    assert "tas wanita" not in teks
    assert "- tas: kategori tas, udara belum diputuskan" in teks


def test_format_konteks():
    bank = bangun_bank(BANK_CHAT, embed_palsu)
    teks = format_konteks(bank[:3])
    assert "- tas wanita: kategori tas, udara non-branded" in teks
    assert "- baju anak: kategori garmen, udara belum diputuskan" in teks
    assert "- sepatu: kategori belum diputuskan, udara branded" in teks
    assert format_konteks([]) == ""


def test_konteks_masuk_prompt_dan_kunci_cache():
    tanpa, k1 = _system_dan_kunci("pelanggan: tas", "v7", "m")
    dengan, k2 = _system_dan_kunci("pelanggan: tas", "v7", "m", "Contoh keputusan admin: X")
    assert "Contoh keputusan admin: X" in dengan and "Contoh keputusan admin" not in tanpa
    assert dengan.endswith(tanpa[tanpa.index("\nSkema JSON:"):])     # skema tetap di akhir
    assert k1 != k2
