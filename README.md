# Ekstraksi Pesanan dari Chat Cargo

Mengubah chat WhatsApp pelanggan forwarding China → Indonesia menjadi data pesanan terstruktur,
lalu membuat pertanyaan balik untuk info yang kurang. Berjalan **lokal dan gratis** dengan model
open-source (Ollama), dan **dievaluasi pada chat asli** dari bisnis keluarga (Pelita Cargo).

```
chat ──► buang template ──► LLM lokal ──► EkstraksiLLM ──► validator ──► Pesanan + pertanyaan balik
         (quick reply admin)  (qwen3.5:9b)   apa yang         (kode Python: satuan, CBM, cek wajar,
                                             dikatakan        minimum tarif, alias kota, info kurang)
```

Contoh: `一共5件，每件 50*50*40，总重 160斤，大概0.5方，到泗水` → 5 koli, 50×50×40 cm, 80 kg, 0,5 CBM,
Surabaya, lalu pertanyaan balik dalam bahasa pelanggan: `走海运还是空运？`

## Masalahnya

Admin menerima ±20 pertanyaan harga per minggu. Info pelanggan pendek, tersebar di beberapa pesan,
bercampur dengan template admin, dan sering tidak lengkap. Pola khasnya (contoh sintetis): satu
pesan "60 × 50 × 40 cm brp kak?" plus foto, lalu "beratnya 20an kg" dan "kirim ke Medan ya" di hari
berikutnya. Admin harus menyalin angka, menghitung CBM, memilih kategori tarif, lalu menanyakan yang
kurang.

## Keputusan desain

- **LLM hanya membaca, kode yang menghitung.** Model menyalin angka dan satuan apa adanya (斤, m, mm).
  Konversi, CBM, minimum tarif, dan cek kewajaran dikerjakan Python biasa yang diuji tanpa model.
  Validator menangkap kesalahan model, misalnya berat 0,1 kg untuk 0,1 CBM (densitas 1 kg/m³).
- **Lokal, tanpa API berbayar.** `qwen3.5:9b` lewat Ollama di CPU laptop (±40–60 detik per chat).
  Output dibatasi skema Pydantic (structured output).
- **Urutan kolom skema berpengaruh.** Model mengisi JSON dari atas. Saat `jumlah_koli` ada di depan
  ukuran, "65 × 45 × 50 cm" dibaca sebagai 65 koli. Memindahkan ukuran ke depan memperbaikinya;
  menambah contoh di prompt tidak berpengaruh. Kedua perubahan diuji terpisah, dan ada tes yang
  menjaga urutan ini.
- **Template admin dibuang sebelum dikirim ke model.** Quick reply (pricelist, cara kirim, alamat
  gudang) membuat model mengarang kota "Jakarta" dan membaca "20pcs" sebagai 20 koli.
- **Privasi.** Chat asli disamarkan berbasis aturan (nama, nomor HP termasuk tanpa kode negara,
  rekening, WeChat, alamat sampai tingkat kelurahan, marking, nomor dokumen), lalu diperiksa otomatis
  dan dibaca manual. Chat asli, hasil samaran, dan hasil evaluasinya tidak pernah di-commit. Halaman
  Streamlit hanya terbuka di localhost.

## Data dan cara melabel

- **Sumber:** 26 ekspor WhatsApp, dipotong menjadi 30 episode percakapan. Satu contoh data = satu
  permintaan harga.
- **Titik potong:** input berhenti tepat sebelum admin memberi harga untuk barang itu. Tanpa ini,
  model bisa "menyontek" jawaban admin (hitungan CBM, kategori). Label hanya berisi apa yang
  dikatakan pelanggan sebelum titik potong. Kategori dan branded adalah keputusan tarif admin.
- **Split:** 5 episode dev (dipakai selama memperbaiki prompt), 23 episode test (dilabel setelah
  prompt dibekukan), dan 4 chat sintetis untuk kasus Mandarin/Inggris.
- **Alat:** `app/tandai.py` untuk menandai jenis episode dan titik potong (dengan saran otomatis),
  dan `app/label.py` untuk melabel dengan isian awal yang dikoreksi admin. Aturannya ada di
  [`docs/panduan_label.md`](docs/panduan_label.md).

## Hasil (test: 23 chat asli)

| Kolom | v6 (prompt beku) | v7 (+ tabel kategori Pelita) |
|---|---|---|
| Jumlah koli | 100% | 100% |
| CBM | 100% | 100% |
| Kota tujuan | 100% | 100% |
| Ukuran (grup koli) | 96% | 96% |
| Jalur (laut/udara) | 91% | 91% |
| Berat | 87% | 100% |
| Jenis barang | 74% | 74% |
| Branded (tarif udara) | 60% | 60% |
| Kategori (tarif laut) | 6% | **35%** |
| Info kurang (set persis sama) | 65% | 78% |
| **Chat benar di semua kolom** | **5/23** | **9/23** |

Kolom v7 diukur dengan kode di repo ini. Sebelum commit pertama, satu contoh angka di docstring
skema diganti angka buatan (privasi). Docstring itu ikut masuk prompt, dan perubahan sekecil itu
saja sudah mengubah output mentah di 19 dari 28 chat. Status per kolom berubah di 4 chat (v7 sebelumnya:
8/23). Jadi selisih 1–3 chat antarversi masih dalam batas noise.

Cara membaca:
- Info yang **diucapkan pelanggan** (koli, CBM, kota, ukuran, jalur, berat) sudah kuat.
- Yang lemah adalah **keputusan tarif admin**. Kategori lartas ringan/berat mengikuti aturan impor
  yang samar, dan model cenderung menebak "umum".
- Jenis barang sering terlewat kalau disebut di kalimat biasa, bukan di formulir.
- Setiap kolom dipisah menjadi benar / salah / halusinasi / terlewat. Daftar kegagalan per chat
  disimpan untuk analisis.
- Evaluasi juga menemukan satu **kesalahan label** (pelanggan menulis "ke Jakarta" tapi label
  kosong); label itu dikoreksi dan dicatat.

## Eksperimen: contoh dari riwayat keputusan admin (retrieval)

Model tidak dilatih ulang; pengetahuan admin dimasukkan lewat prompt. Untuk tiap chat, sistem mencari
chat berlabel lain yang mirip (embedding lokal `qwen3-embedding:0.6b`). Keputusan admin di chat itu
(jenis barang → kategori, branded) lalu ditambahkan ke prompt v7. Pengukuran pakai leave-one-out:
contoh dari pelanggan (ekspor) yang sama tidak pernah dipakai. Bank berisi 21 contoh.

| 23 chat test | v7 | v7 + 5 contoh termirip | v7 + semua contoh |
|---|---|---|---|
| Kategori | 35% | 35% | 47% |
| Branded | 60% | 60% | 55% |
| Jalur | 91% | 87% | 83% |
| Info kurang | 78% | 65% | 65% |
| Chat benar di semua kolom | **9/23** | 6/23 | 7/23 |

Hasilnya **tidak lebih baik**, jadi tidak dipakai sebagai bawaan (`--riwayat` tetap tersedia):
- Barang pelanggan hampir semuanya unik, jadi contoh "termirip" sering hanya kebetulan
  (kemiripan nama barang 0,56–0,74).
- Teks tambahan mengganggu kolom lain (jalur, info kurang) pada model 9B.
- Semua kesalahan kategori sama polanya: admin memutuskan lartas, model menebak "umum".
  Tebakan "lartas ringan" untuk semua chat saja sudah 55%. Masalahnya ada pada batas "umum" di
  prompt, bukan kurang contoh.

Perlu diukur ulang setelah data berlabel bertambah.

## Keterbatasan

- Test hanya 23 chat dan sudah dipakai beberapa kali (v6, v7, eksperimen retrieval). Satu chat = ±4%.
- Semua chat asli berbahasa **Indonesia**. Kemampuan Mandarin/Inggris baru diuji dengan data
  sintetis.
- Tahap 1 hanya teks. Info yang hanya ada di foto (jenis barang, packing list) belum dibaca.
- Kategori lartas masih lemah (lihat eksperimen retrieval di atas).

## Menjalankan

Butuh Python 3.12+ dan [Ollama](https://ollama.com).

```bash
py -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
ollama pull qwen3.5:9b
ollama pull qwen3-embedding:0.6b   # hanya untuk eksperimen --riwayat
pytest
streamlit run app/streamlit_app.py           # demo, contoh chat sintetis di sidebar
python -m evaluasi.jalankan --split dev      # evaluasi pada chat sintetis
```

Alur chat asli (semua hasilnya di `data/privat/`, tidak di-commit):

```bash
python scripts/impor_whatsapp.py data/raw/<folder>/chat.txt --nama <nama admin>
streamlit run app/tandai.py      # jenis episode + titik potong
streamlit run app/label.py       # label (isian awal dikoreksi admin)
python -m evaluasi.jalankan --split asli-test
python -m evaluasi.bandingkan <folder_run_a> <folder_run_b>
```

## Struktur

| Folder | Isi |
|---|---|
| `src/cargo_extract/` | skema, pembaca WhatsApp, penyamar, buang template, extractor, validator, pertanyaan balik, pipeline |
| `prompts/` | versi prompt v1–v7 (baku: v7) |
| `evaluasi/` | menjalankan evaluasi, metrik per kolom, membandingkan run |
| `app/` | demo, halaman tandai, halaman label |
| `data/chats/` | chat sintetis berlabel |
| `data/referensi/` | alias kota, frasa template admin, kategori tarif (tanpa harga) |
| `data/raw/`, `data/privat/` | chat asli dan turunannya, **tidak di-commit** |
| `docs/` | panduan label |
| `tests/` | 58 tes (tanpa memanggil model) |

Riwayat keputusan lengkap disimpan di catatan kerja internal (`KONTEKS_PROYEK.md`, tidak
dipublikasikan karena memuat detail chat asli).
