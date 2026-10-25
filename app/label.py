"""Melabel episode chat asli: draft dari model, dikoreksi manual.

    streamlit run app/label.py

Hanya episode bertanda 'permintaan harga' (app/tandai.py). Label disimpan di data/privat/label.json,
lalu dataset evaluasi dibangun ulang ke data/privat/dataset/asli.jsonl. Aturan: docs/panduan_label.md.
"""
import pandas as pd
import streamlit as st
from pydantic import ValidationError

from cargo_extract import config
from cargo_extract.bersihkan import buang_template
from cargo_extract.dataset import teks_chat
from cargo_extract.extractor import dari_cache, ekstrak
from cargo_extract.label import (
    TAGS,
    bangun_dataset,
    file_draft_label,
    id_dev,
    info_kurang_dari_label,
    muat_label,
    simpan_label,
)
from cargo_extract.satuan import cbm as hitung_cbm
from cargo_extract.schemas import Bahasa, GrupKoli, Jalur, KategoriBarang, LabelManual, LabelPesanan
from cargo_extract.tanda import input_episode, muat_draft, muat_tanda
from cargo_extract.validator import alias_kota, normalisasi

PROMPT_DRAFT = config.PROMPT_BAKU
KOLOM_GRUP = ["jumlah_koli", "p_cm", "l_cm", "t_cm", "berat_per_koli_kg"]

def angka(judul: str, awal: float | None, key: str, bulat: bool = False) -> float | int | None:
    """Kotak teks untuk angka yang boleh kosong (st.number_input tidak bisa dikosongkan lagi)."""
    teks = st.text_input(judul, "" if awal is None else f"{awal:g}", key=key,
                         placeholder="kosong = tidak disebut").strip().replace(",", ".")
    if not teks:
        return None
    try:
        nilai = float(teks)
    except ValueError:
        galat.append(f"{judul}: '{teks}' bukan angka")
        return None
    if nilai <= 0 or (bulat and not nilai.is_integer()):
        galat.append(f"{judul}: harus {'bilangan bulat ' if bulat else ''}lebih dari 0")
        return None
    return int(nilai) if bulat else nilai


st.set_page_config(page_title="Label episode", layout="wide")
st.title("Label episode chat")

tanda = muat_tanda()
drafts = {d.id: d for f in sorted(config.PRIVAT_DIR.glob("*.jsonl")) for d in muat_draft(f)}
ids = [i for i in drafts if i in tanda and tanda[i].jenis == "permintaan_harga"]
if not ids:
    st.info("Belum ada episode bertanda 'permintaan harga'. Tandai dulu di app/tandai.py.")
    st.stop()

label = muat_label()
selesai = sum(i in label for i in ids)
st.sidebar.progress(selesai / len(ids), text=f"{selesai}/{len(ids)} episode dilabel")
id_ep = st.sidebar.radio("Episode", ids, format_func=lambda i: f"{'✅' if i in label else '⬜'} {i}")

d, t = drafts[id_ep], tanda[id_ep]
pesan = input_episode(d, t)
teks_model = teks_chat(buang_template(pesan))   # sama dengan yang dikirim ke model saat evaluasi
raw = dari_cache(teks_model, PROMPT_DRAFT)
draft = normalisasi(raw) if raw else None
tersimpan = label.get(id_ep)
usulan = muat_label(file_draft_label()).get(id_ep)   # draft label yang belum diverifikasi
if tersimpan:
    awal = tersimpan.label
elif usulan:
    awal = usulan.label
elif draft:
    awal = LabelPesanan.model_validate(draft.model_dump(include=set(LabelPesanan.model_fields)))
else:
    awal = LabelPesanan()

kiri, kanan = st.columns([3, 2], gap="large")

with kiri:
    def tampilkan(i: int) -> None:
        p = d.pesan[i]
        pelanggan = p.pengirim == "pelanggan"
        with st.chat_message("user" if pelanggan else "assistant", avatar="🧑" if pelanggan else "🏢"):
            st.caption(f"#{i} · {p.pengirim}" + (f" · {p.waktu:%d %b %H:%M}" if p.waktu else ""))
            st.text(p.teks)

    st.subheader(f"Input ke model: {len(pesan)} pesan")
    for i in range(len(pesan)):
        tampilkan(i)
    if len(pesan) < len(d.pesan):
        with st.expander(f"✂️ {len(d.pesan) - len(pesan)} pesan setelah titik potong (hanya untuk kategori)"):
            for i in range(len(pesan), len(d.pesan)):
                tampilkan(i)

with kanan:
    k = id_ep   # akhiran key widget, supaya isian tiap episode terpisah
    if usulan and not tersimpan:
        st.info("Isian awal = draft label dari Claude (bukan dari model). Cek setiap kolom, lalu Simpan.")
    if draft:
        if not (usulan or tersimpan):
            st.caption(f"Isian awal = draft model ({PROMPT_DRAFT}). Periksa setiap kolom, jangan langsung percaya.")
        for p in draft.peringatan:
            st.warning(f"{p.kode.value}: {p.pesan}")
        for c in raw.catatan_ambigu:
            st.caption(f"? {c}")
    elif not tersimpan:
        st.info("Draft model belum ada. Bisa isi manual, atau buat draft dulu.")
        if st.button("Buat draft dari model (±1–2 menit)", key=f"draft_{k}"):
            with st.spinner("Model membaca chat..."):
                ekstrak(teks_model, PROMPT_DRAFT)
            st.rerun()

    jenis = st.text_input("Jenis barang", awal.jenis_barang or "", key=f"jenis_{k}").strip().lower() or None
    opsi_kategori = [None, *KategoriBarang]
    kategori = st.selectbox(
        "Kategori (keputusan admin, boleh dari setelah titik potong)", opsi_kategori,
        index=opsi_kategori.index(awal.kategori_barang), key=f"kategori_{k}",
        format_func=lambda v: "(kosong)" if v is None else v.value,
    )
    opsi_branded = [None, True, False]
    branded = st.selectbox(
        "Branded (keputusan tarif udara admin: 230rb = ya, 220rb = tidak)", opsi_branded,
        index=opsi_branded.index(awal.branded), key=f"branded_{k}",
        format_func={None: "(kosong: belum diputuskan / kirim dua tarif)", True: "ya (230rb)",
                     False: "tidak (220rb)"}.get,
    )

    st.markdown("**Grup koli**: satu baris per kelompok koli berukuran sama; ukuran dalam cm.")
    tabel_awal = pd.DataFrame(
        [{"jumlah_koli": g.jumlah_koli,
          **dict(zip(KOLOM_GRUP[1:4], g.dimensi_cm or (None, None, None))),
          "berat_per_koli_kg": g.berat_per_koli_kg} for g in awal.grup_koli],
        columns=KOLOM_GRUP, dtype="float",
    )
    tabel = st.data_editor(
        tabel_awal, num_rows="dynamic", key=f"grup_{k}",
        column_config={
            "jumlah_koli": st.column_config.NumberColumn("koli", min_value=1, step=1, format="%d"),
            "p_cm": st.column_config.NumberColumn("p (cm)", min_value=0.0),
            "l_cm": st.column_config.NumberColumn("l (cm)", min_value=0.0),
            "t_cm": st.column_config.NumberColumn("t (cm)", min_value=0.0),
            "berat_per_koli_kg": st.column_config.NumberColumn("berat/koli (kg)", min_value=0.0),
        },
    )

    galat = []
    grup = []
    for baris in tabel.to_dict("records"):
        v = {c: None if pd.isna(baris[c]) else float(baris[c]) for c in KOLOM_GRUP}
        if all(x is None for x in v.values()):
            continue
        dimensi = (v["p_cm"], v["l_cm"], v["t_cm"])
        try:
            grup.append(GrupKoli(
                jumlah_koli=int(v["jumlah_koli"]) if v["jumlah_koli"] is not None else None,
                dimensi_cm=dimensi if None not in dimensi else None,
                berat_per_koli_kg=v["berat_per_koli_kg"],
            ))
        except ValidationError:
            galat.append(f"Baris grup koli tidak valid: {v}")
        if None in dimensi and any(x is not None for x in dimensi):
            galat.append("Ukuran harus diisi ketiganya (p, l, t) atau dikosongkan semua.")

    lengkap = bool(grup) and all(g.jumlah_koli for g in grup)
    if lengkap:
        jumlah_koli = sum(g.jumlah_koli for g in grup)
        st.caption(f"Jumlah koli: {jumlah_koli} (dihitung dari grup)")
    else:
        jumlah_koli = angka("Jumlah koli total", awal.jumlah_koli, f"koli_{k}", bulat=True)

    berat_dari_koli = (sum(g.jumlah_koli * g.berat_per_koli_kg for g in grup)
                       if lengkap and all(g.berat_per_koli_kg for g in grup) else None)
    berat = angka("Berat total (kg)", awal.berat_kg, f"berat_{k}")
    if berat is None and berat_dari_koli:
        berat = round(berat_dari_koli, 3)
        st.caption(f"Berat total: {berat} kg (per koli × jumlah)")
    elif berat and berat_dari_koli and abs(berat - berat_dari_koli) > 0.02 * berat:
        st.warning(f"Berat total {berat:g} kg ≠ per koli × jumlah = {berat_dari_koli:g} kg")

    if lengkap and all(g.dimensi_cm for g in grup):
        cbm = round(sum(hitung_cbm(g.jumlah_koli, *g.dimensi_cm) for g in grup), 3)
        st.caption(f"CBM: {cbm} (dihitung dari ukuran)")
    else:
        cbm = angka("CBM yang disebut pelanggan", awal.cbm, f"cbm_{k}")

    opsi_kota = [None, *sorted(set(alias_kota().values()))]
    kota = st.selectbox(
        "Kota tujuan", opsi_kota, index=opsi_kota.index(awal.kota_tujuan) if awal.kota_tujuan in opsi_kota else 0,
        key=f"kota_{k}", format_func=lambda v: "(kosong)" if v is None else v,
    )
    if draft and draft.kota_tujuan and draft.kota_tujuan not in opsi_kota:
        st.caption(f"Model menulis '{draft.kota_tujuan}'. Pilih kota/kabupatennya, atau tambahkan ke data/referensi/kota.csv.")
    opsi_jalur = [None, Jalur.LAUT, Jalur.UDARA]
    jalur = st.selectbox(
        "Jalur", opsi_jalur, index=opsi_jalur.index(awal.jalur), key=f"jalur_{k}",
        format_func=lambda v: "(tidak disebut)" if v is None else v.value,
    )

    lab = LabelPesanan(
        jenis_barang=jenis, kategori_barang=kategori, branded=branded, jumlah_koli=jumlah_koli,
        berat_kg=berat, grup_koli=grup, cbm=cbm, kota_tujuan=kota, jalur=jalur,
    )
    lab = lab.model_copy(update={"info_kurang": info_kurang_dari_label(lab)})
    st.markdown("**Info kurang** (otomatis dari isian): "
                + (", ".join(x.value for x in lab.info_kurang) or "tidak ada"))

    sumber_awal = tersimpan or usulan
    bahasa_awal = sumber_awal.bahasa if sumber_awal else [draft.bahasa_pelanggan] if draft else [Bahasa.ID]
    bahasa = st.multiselect("Bahasa pelanggan", list(Bahasa), default=bahasa_awal, key=f"bahasa_{k}",
                            format_func=lambda b: b.value)
    tag = st.multiselect("Tag", TAGS, default=sumber_awal.tag if sumber_awal else [], key=f"tag_{k}")

    for g in galat:
        st.error(g)
    if st.button("Simpan label", type="primary", key=f"simpan_{k}", disabled=bool(galat) or not bahasa):
        simpan_label(id_ep, LabelManual(label=lab, bahasa=bahasa, tag=tag, potong_sebelum=t.potong_sebelum))
        bangun_dataset()
        st.rerun()
    if tersimpan:
        st.success("Label tersimpan.")
        if tersimpan.potong_sebelum != t.potong_sebelum:
            st.warning("Titik potong berubah sejak episode ini dilabel. Cek ulang labelnya.")

dev = id_dev()
st.sidebar.caption(f"Dataset: {sum(i in dev for i in label)} dev, {sum(i not in dev for i in label)} test "
                   "(data/privat/dataset/asli_*.jsonl)")
if id_ep in dev:
    st.sidebar.caption(f"{id_ep} termasuk dev (sudah dipakai untuk memperbaiki prompt).")
