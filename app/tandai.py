"""Menandai episode chat asli: jenis episode dan titik potong input.

    streamlit run app/tandai.py

Aturannya: docs/panduan_label.md, bagian "Chat asli". Tanda disimpan di data/privat/tanda.json.
"""
import streamlit as st

from cargo_extract import config
from cargo_extract.schemas import TandaEpisode
from cargo_extract.tanda import muat_draft, muat_tanda, saran_titik_potong, simpan_tanda

JENIS = {
    "permintaan_harga": "Permintaan harga (masuk dataset)",
    "tindak_lanjut": "Tindak lanjut order",
    "lainnya": "Lainnya",
}

st.set_page_config(page_title="Tandai episode", layout="wide")
st.title("Tandai episode chat")

files = sorted(config.PRIVAT_DIR.glob("*.jsonl"))
if not files:
    st.info("Belum ada draft di data/privat/. Jalankan scripts/impor_whatsapp.py dulu.")
    st.stop()

tanda = muat_tanda()
file = st.sidebar.selectbox("Ekspor", files, format_func=lambda p: p.stem)
drafts = {d.id: d for d in muat_draft(file)}
selesai = sum(i in tanda for i in drafts)
st.sidebar.progress(selesai / len(drafts), text=f"{selesai}/{len(drafts)} episode ditandai")
id_ep = st.sidebar.radio(
    "Episode", list(drafts),
    format_func=lambda i: f"{'✅' if i in tanda else '⬜'} {i} ({len(drafts[i].pesan)} pesan)",
)

d, t = drafts[id_ep], tanda.get(id_ep)
saran = saran_titik_potong(d.pesan)
kiri, kanan = st.columns([3, 2], gap="large")

with kanan:
    jenis = st.radio(
        "Jenis episode", list(JENIS), format_func=JENIS.get,
        index=list(JENIS).index(t.jenis) if t else 0, key=f"jenis_{id_ep}",
    )
    opsi = [*range(len(d.pesan)), None]
    awal = t.potong_sebelum if t else saran
    potong = st.selectbox(
        "Potong sebelum pesan", opsi, index=opsi.index(awal if awal in opsi else saran),
        format_func=lambda i: "Tidak dipotong (seluruh episode)" if i is None
        else f"#{i} {d.pesan[i].pengirim}: {' / '.join(b.strip() for b in d.pesan[i].teks.splitlines() if b.strip())[:60]}",
        key=f"potong_{id_ep}", disabled=jenis != "permintaan_harga",
    )
    if saran is None:
        st.caption("Saran otomatis: admin belum menjawab harga di episode ini.")
    else:
        st.caption(f"Saran otomatis: sebelum #{saran}. Pricelist umum tidak dihitung sebagai jawaban.")
    catatan = st.text_input("Catatan", value=t.catatan if t else "", key=f"catatan_{id_ep}")
    if st.button("Simpan", type="primary", key=f"simpan_{id_ep}"):
        dipotong = potong if jenis == "permintaan_harga" else None
        simpan_tanda(id_ep, TandaEpisode(jenis=jenis, potong_sebelum=dipotong, catatan=catatan))
        st.rerun()
    if t:
        st.success(f"Tersimpan: {JENIS[t.jenis]}"
                   + (f", dipotong sebelum #{t.potong_sebelum}" if t.potong_sebelum is not None else ""))

with kiri:
    batas = potong if jenis == "permintaan_harga" and potong is not None else len(d.pesan)

    def tampilkan(i: int) -> None:
        p = d.pesan[i]
        pelanggan = p.pengirim == "pelanggan"
        with st.chat_message("user" if pelanggan else "assistant", avatar="🧑" if pelanggan else "🏢"):
            st.caption(f"#{i} · {p.pengirim}" + (f" · {p.waktu:%d %b %H:%M}" if p.waktu else ""))
            st.text(p.teks)

    st.subheader(f"Input ke model: {batas} pesan")
    for i in range(batas):
        tampilkan(i)
    if batas < len(d.pesan):
        with st.expander(f"✂️ {len(d.pesan) - batas} pesan setelah titik potong (tidak masuk input)"):
            for i in range(batas, len(d.pesan)):
                tampilkan(i)
