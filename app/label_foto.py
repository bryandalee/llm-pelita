"""Tahap 2: cek label jenis barang setelah melihat foto pelanggan.

    streamlit run app/label_foto.py

Hanya episode berlabel yang punya file foto pelanggan sebelum titik potong. Isian awal dari
data/privat/draft_label_foto.json; yang disimpan masuk data/privat/label_foto.json.
"""
import streamlit as st

from cargo_extract.dataset import muat_chats
from cargo_extract.foto import path_foto
from cargo_extract.label import file_dataset, file_label_foto, muat_label_foto, simpan_label_foto

st.set_page_config(page_title="Label foto", layout="wide")
st.title("Jenis barang dengan foto")

chats = {c.id: c for s in ("dev", "test") for c in muat_chats(file_dataset(s))
         if any(path_foto(p) for p in c.pesan)}
label, usulan = muat_label_foto(), muat_label_foto(file_label_foto(draft=True))
st.sidebar.progress(sum(i in label for i in chats) / len(chats), text=f"{sum(i in label for i in chats)}/{len(chats)} dicek")
id_ep = st.sidebar.radio("Episode", list(chats), format_func=lambda i: f"{'✅' if i in label else '⬜'} {i}")
c = chats[id_ep]

kiri, kanan = st.columns([3, 2], gap="large")
with kiri:
    for p in c.pesan:
        pelanggan = p.pengirim == "pelanggan"
        with st.chat_message("user" if pelanggan else "assistant", avatar="🧑" if pelanggan else "🏢"):
            st.text(p.teks)
            for f in path_foto(p):
                st.image(str(f), width=360)

with kanan:
    st.caption(f"Label tahap 1 (teks saja): {c.label.jenis_barang or '(kosong)'}")
    awal = label.get(id_ep, usulan.get(id_ep)) or ""
    jenis = st.text_input("Jenis barang (teks + foto)", awal, key=f"jenis_{id_ep}",
                          help="Nama lain yang juga benar dipisah |, mis. 'steering wheel buttons | tombol setir'. "
                               "Kosongkan jika barang tetap tidak bisa dikenali.").strip().lower() or None
    if st.button("Simpan", type="primary"):
        simpan_label_foto(id_ep, jenis)
        st.rerun()
    if id_ep in label:
        st.success(f"Tersimpan: {label[id_ep] or '(kosong)'}")
