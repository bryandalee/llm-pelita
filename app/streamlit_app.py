"""Demo: tempel chat -> lihat data pesanan, peringatan, dan pertanyaan balik.

    streamlit run app/streamlit_app.py

Model berjalan lokal lewat Ollama. Contoh chat di sidebar adalah data sintetis.
"""
import pandas as pd
import streamlit as st

from cargo_extract import config
from cargo_extract.dataset import format_chat, muat_chats, parse_teks_chat
from cargo_extract.pipeline import proses

st.set_page_config(page_title="Ekstraksi Pesanan Cargo", layout="wide")
st.title("Ekstraksi Pesanan Cargo")
st.caption(f"Chat pelanggan (Indonesia/Mandarin/Inggris) → data pesanan. Model lokal: {config.MODEL_ID}, "
           f"prompt {config.PROMPT_BAKU}. Tidak ada data yang dikirim ke luar laptop.")

contoh = {c.id: c for c in muat_chats(config.DATA_DIR / "chats" / "dev.jsonl")}
pilihan = st.sidebar.selectbox("Contoh chat (sintetis)", ["(tulis sendiri)", *contoh])
if pilihan != "(tulis sendiri)" and st.session_state.get("contoh_dipilih") != pilihan:
    st.session_state["contoh_dipilih"] = pilihan
    st.session_state["chat"] = format_chat(contoh[pilihan])

teks = st.text_area(
    "Chat (satu pesan per baris, awali dengan 'pelanggan:' atau 'admin:')", key="chat", height=180,
    placeholder="pelanggan: kak mau kirim sepatu 3 dus 60x40x40 ke Surabaya",
)
if st.button("Ekstrak", type="primary", disabled=not teks.strip()):
    with st.spinner("Model membaca chat... (panggilan pertama bisa 1–2 menit)"):
        st.session_state["hasil"] = proses(parse_teks_chat(teks))

if "hasil" in st.session_state:
    pesanan, raw = st.session_state["hasil"]
    kiri, kanan = st.columns(2, gap="large")
    with kiri:
        st.subheader("Data pesanan")
        baris = {
            "Jenis barang": pesanan.jenis_barang or "–",
            "Kategori (tarif laut)": pesanan.kategori_barang.value if pesanan.kategori_barang else "–",
            "Branded (tarif udara)": {None: "–", True: "ya", False: "tidak"}[pesanan.branded],
            "Jumlah koli": pesanan.jumlah_koli or "–",
            "Berat total (kg)": f"{pesanan.berat_kg:g}" if pesanan.berat_kg else "–",
            "Ukuran per koli (cm)": ", ".join(
                f"{g.jumlah_koli or '?'} × {'x'.join(f'{s:g}' for s in g.dimensi_cm)}"
                for g in pesanan.grup_koli if g.dimensi_cm) or "–",
            "CBM": f"{pesanan.cbm:g} ({pesanan.cbm_sumber})" if pesanan.cbm else "–",
            "Kota tujuan": pesanan.kota_tujuan or "–",
            "Jalur": pesanan.jalur.value if pesanan.jalur else "–",
        }
        st.table(pd.DataFrame({"Nilai": [str(v) for v in baris.values()]}, index=list(baris)))
    with kanan:
        st.subheader("Pertanyaan balik")
        if pesanan.pertanyaan_balik:
            st.code(pesanan.pertanyaan_balik, language=None, wrap_lines=True)
        else:
            st.success("Info lengkap, siap dihitung ongkirnya.")
        if pesanan.peringatan:
            st.subheader("Peringatan validator")
            for p in pesanan.peringatan:
                st.warning(f"{p.kode.value}: {p.pesan}")
        for c in raw.catatan_ambigu:
            st.caption(f"Catatan model: {c}")
    with st.expander("JSON lengkap"):
        st.json(pesanan.model_dump(mode="json"))
