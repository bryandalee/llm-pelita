"""Demo: chat WhatsApp -> data pesanan, peringatan, dan pertanyaan balik.

    streamlit run app/streamlit_app.py

Chat bisa ditempel apa adanya (salin pesan dari WhatsApp Desktop/Web) atau diunggah sebagai file
ekspor (.txt, atau .zip berikut fotonya). Sistem memisahkan pesan admin dan pelanggan sendiri; foto
barang bisa ditambahkan. Model berjalan lokal lewat Ollama, jadi tidak ada data yang dikirim ke luar
laptop. File unggahan hanya disimpan di folder sementara. Contoh chat di sidebar adalah data sintetis.
"""
import shutil
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

from cargo_extract import config
from cargo_extract.bersihkan import frasa_template
from cargo_extract.dataset import format_chat, muat_chats, parse_teks_chat
from cargo_extract.foto import baca_foto, path_foto
from cargo_extract.pipeline import proses
from cargo_extract.schemas import Lampiran, Pesan
from cargo_extract.whatsapp import baca_teks, pengirim, potong_episode, tebak_admin

st.set_page_config(page_title="Ekstraksi Pesanan Cargo", layout="wide")
st.title("Ekstraksi Pesanan Cargo")
st.caption(f"Chat pelanggan (Indonesia/Mandarin/Inggris) → data pesanan. Model lokal: {config.MODEL_ID}, "
           f"prompt {config.PROMPT_BAKU}. Tidak ada data yang dikirim ke luar laptop.")


def folder_sesi(nama: str) -> Path:
    """Folder sementara per sesi untuk file unggahan; dikosongkan setiap kali diisi ulang."""
    if "folder" not in st.session_state:
        st.session_state["folder"] = Path(tempfile.mkdtemp(prefix="demo_cargo_"))
    folder = st.session_state["folder"] / nama
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    return folder


def teks_ekspor(berkas, folder: Path) -> str:
    """Isi chat dari file ekspor; media di dalam .zip disalin ke `folder` (nama file saja)."""
    if not berkas.name.lower().endswith(".zip"):
        return berkas.getvalue().decode("utf-8-sig", errors="replace")
    teks = ""
    with zipfile.ZipFile(berkas) as z:
        for info in z.infolist():
            nama = Path(info.filename).name
            if not nama or info.is_dir():
                continue
            if nama.lower().endswith(".txt"):
                teks = z.read(info).decode("utf-8-sig", errors="replace")
            else:
                (folder / nama).write_bytes(z.read(info))
    return teks


def pilih_admin(teks: str, key: str) -> set[str]:
    nama = pengirim(teks)
    tebakan = tebak_admin(teks, frasa_template())
    return set(st.multiselect(
        "Pengirim yang admin (sisanya dianggap pelanggan)", nama, default=[n for n in nama if n in tebakan],
        key=key, help="Ditebak dari nama 'You'/'Anda' atau pesan template admin. Cukup dicek sekali."))


contoh = {c.id: c for c in muat_chats(config.DATA_DIR / "chats" / "dev.jsonl")}
pilihan = st.sidebar.selectbox("Contoh chat (sintetis)", ["(tulis sendiri)", *contoh])
if pilihan != "(tulis sendiri)" and st.session_state.get("contoh_dipilih") != pilihan:
    st.session_state["contoh_dipilih"] = pilihan
    st.session_state["chat"] = format_chat(contoh[pilihan])
    st.session_state["sumber"] = "Tempel chat"

sumber = st.radio("Sumber chat", ["Tempel chat", "Unggah file ekspor"], horizontal=True, key="sumber")
pesan: list[Pesan] = []
if sumber == "Tempel chat":
    teks = st.text_area(
        "Tempel pesan yang disalin dari WhatsApp (pilih pesan → salin → tempel), atau tulis 'pelanggan: ...'",
        key="chat", height=200,
        placeholder="[09:15, 20/10/2026] Toko Maju: kak mau kirim sepatu 3 dus 60x40x40 ke Surabaya")
    if pengirim(teks):
        pesan = baca_teks(teks, pilih_admin(teks, "admin_tempel")).pesan
    elif teks.strip():
        pesan = parse_teks_chat(teks)
else:
    berkas = st.file_uploader("File ekspor chat WhatsApp (.txt, atau .zip yang berisi foto)", type=["txt", "zip"])
    if berkas:
        folder = folder_sesi("ekspor")
        teks = teks_ekspor(berkas, folder)
        episode = potong_episode(baca_teks(teks, pilih_admin(teks, "admin_ekspor"), folder_media=str(folder)).pesan)
        if episode:
            i = st.selectbox("Percakapan (dipotong jika ada jeda 7 hari)", range(len(episode)), index=len(episode) - 1,
                             format_func=lambda i: f"{episode[i][0].waktu:%d %b %Y} · {len(episode[i])} pesan")
            pesan = episode[i]
        else:
            st.error("Tidak ada pesan yang dikenali di file ini.")

foto = st.file_uploader("Foto barang dari pelanggan (opsional)", type=["jpg", "jpeg", "png", "webp"],
                        accept_multiple_files=True)
if foto and pesan:
    folder = folder_sesi("foto")
    lampiran = []
    for f in foto:
        (folder / f.name).write_bytes(f.getvalue())
        lampiran.append(Lampiran(jenis="foto", file=str(folder / f.name)))
    terakhir = max((i for i, p in enumerate(pesan) if p.pengirim == "pelanggan"), default=None)
    tambahan = Pesan(pengirim="pelanggan", teks=" ".join("[foto]" for _ in lampiran), lampiran=lampiran)
    pesan = pesan + [tambahan] if terakhir is None else [
        p.model_copy(update={"teks": f"{p.teks}\n{tambahan.teks}", "lampiran": [*p.lampiran, *lampiran]})
        if i == terakhir else p for i, p in enumerate(pesan)]

if pesan:
    n_pelanggan = sum(p.pengirim == "pelanggan" for p in pesan)
    with st.expander(f"Pembagian pesan: {n_pelanggan} pelanggan, {len(pesan) - n_pelanggan} admin"):
        st.dataframe(pd.DataFrame({"pengirim": [p.pengirim for p in pesan],
                                   "pesan": [p.teks[:120] for p in pesan]}), hide_index=True)
    if not n_pelanggan:
        st.warning("Belum ada pesan pelanggan. Cek pilihan admin di atas.")

ada_foto = any(path_foto(p) for p in pesan)
baca = st.toggle("Baca foto barang", value=ada_foto, disabled=not ada_foto,
                 help="Foto dibaca model yang sama; sekitar 30–40 detik per foto di CPU laptop.")
# Hasil hanya ditampilkan untuk input yang sama persis; ganti chat/foto = hasil lama disembunyikan.
input_sekarang = (repr([(p.pengirim, p.teks, [l.file for l in p.lampiran]) for p in pesan]), baca and ada_foto)
if st.button("Ekstrak", type="primary", disabled=not pesan):
    with st.spinner("Model membaca chat" + (" dan foto" if baca and ada_foto else "") + "... (bisa 1–2 menit)"):
        hasil = proses(pesan, foto=baca and ada_foto)
        st.session_state["foto_dibaca"] = [(f, baca_foto(f)) for p in pesan for f in path_foto(p)] if baca else []
        st.session_state["hasil"] = hasil
        st.session_state["hasil_untuk"] = input_sekarang

if "hasil" in st.session_state and st.session_state.get("hasil_untuk") == input_sekarang:
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
        for path, isi in st.session_state.get("foto_dibaca", []):
            if path.exists():
                st.image(str(path), caption=f"Foto terbaca: {isi}", width=220)
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
