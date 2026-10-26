# Panduan Label (draft)

Aturan ini dipakai untuk melabel setiap chat, supaya label konsisten. Ubah di sini dulu
sebelum mengubah cara melabel.

## Prinsip

- Label berisi **kebenaran**, bukan apa yang ditulis model.
- Kalau pelanggan merevisi ("eh salah, 4 ctn ya"), pakai nilai **terakhir**.
- Kalau sebuah nilai tidak disebut dan tidak bisa dipastikan, isi `null`. Jangan menebak.
- Angka pengandaian ("kalau misal aku pesen 0.1cbm") bukan data kiriman: isi `null` + tag
  `pengandaian`.
- Angka berupa rentang ("Berat: 10-20", "3-4 kg") tidak bisa diisi satu nilai: isi `null` + tag
  `rentang`. Perkiraan satu angka ("20an kg", "mungkin 5kg") tetap diisi + tag `perkiraan`.
- pcs/buah adalah jumlah barang, bukan koli. "1 barang" juga bukan jumlah koli.

## Chat asli: episode dan titik potong

Alur: ekspor WhatsApp → `scripts/impor_whatsapp.py` (dipotong per episode dan disamarkan ke
`data/privat/`) → tandai setiap episode di `streamlit run app/tandai.py` → baru dilabel.

1. **Satu contoh data = satu permintaan harga.** Setiap episode diberi jenis:
   - `permintaan_harga`: pelanggan menanyakan ongkir/harga untuk kirimannya. Masuk dataset.
   - `tindak_lanjut`: lanjutan order (kode marking, packing list, barang sampai, estimasi tiba).
     Tidak masuk dataset ekstraksi.
   - `lainnya`: selain dua jenis di atas. Tidak masuk dataset.
2. **Titik potong.** Input dipotong tepat **sebelum** pesan admin pertama yang memberi harga
   **yang sudah disesuaikan untuk barang pelanggan itu**. Contohnya:
   - hitungan CBM;
   - satu tarif laut yang sudah dipilihkan ("VIA LAUT … 7 jt / cbm");
   - total ongkir ("1.030.000 untuk baju").
   Pricelist yang sudah dipersempit juga dihitung sebagai jawaban, mis. tarif udara lengkap +
   hanya tarif garmen untuk laut.
   - Pricelist umum (semua kategori laut, atau pasangan tarif udara branded/non-branded saja),
     sapaan otomatis, dan penjelasan cara kirim bukan titik potong. Pesan-pesan itu tetap masuk
     input.
   - Jika admin belum pernah menjawab harga di episode itu, tidak dipotong (seluruh episode).
   - Halaman penanda memberi saran otomatis; selalu cek dan perbaiki bila salah.
3. **Label = info dari pelanggan di dalam input** (sebelum titik potong). Info yang baru diberikan
   setelah titik potong tidak dilabel, walaupun lebih lengkap. Kalau ada, beri tag
   `info_setelah_potong`.
4. **Tahap 1 hanya teks.** Info yang hanya ada di foto (mis. jenis barang) tidak dilabel; beri tag
   `ada_gambar`.
5. **Kategori** ditentukan admin, bukan disebut pelanggan. Isi kategori tarif laut barang itu
   menurut admin: dari pesan admin di mana pun dalam episode (termasuk setelah titik potong), atau
   dari pengetahuan admin walaupun tidak tertulis di chat (mis. admin hanya memberi harga udara,
   tapi tahu barangnya lartas ringan). Jika jenis barang di label kosong (mis. barang hanya ada di
   foto), kategori tetap diisi, tetapi tidak dinilai otomatis. Jika admin tidak tahu atau ragu, isi
   `null` + `kategori_perlu_dicek`.
6. **Catatan gudang admin** ("Marking / No.PL / Jmlh Koli / Cbm / KG") adalah hasil ukur gudang,
   bukan yang dikatakan pelanggan. Jangan dipakai sebagai label ekstraksi.

## Per kolom

| Kolom | Aturan |
|---|---|
| `jenis_barang` | nama singkat, huruf kecil ("baju anak", "sparepart motor"). Kalau pelanggan memakai bahasa lain, tulis nama aslinya **dan** terjemahannya, dipisah `\|` ("steering wheel buttons \| tombol setir"); semua nama itu dianggap benar. Urutan kata tidak dinilai |
| `kategori_barang` | kategori tarif laut menurut sifat barang, diisi juga untuk kiriman udara. Kalau ragu, `null` + tag `kategori_perlu_dicek` (kolom ini lalu tidak dinilai untuk chat itu) |
| `branded` | keputusan tarif udara admin: 230rb/kg = `true`, 220rb/kg = `false` (boleh dari setelah titik potong, seperti kategori). Jika admin mengirim keduanya (pricelist), `null`, kecuali pelanggan sendiri menyebut merek. Tidak dinilai jika jenis barang kosong |
| `jumlah_koli` | jumlah koli/ctn/dus/件/箱 seluruh kiriman. **Bukan** jumlah pcs |
| `berat_kg` | berat kotor seluruh kiriman dalam kg. 斤 × 0,5. Jika hanya per koli: per koli × jumlah. Perkiraan ("20an kg kurang lebih") diisi angkanya + tag `perkiraan` |
| `grup_koli` | satu item per kelompok koli berukuran sama; `dimensi_cm` = [p, l, t] dalam cm |
| `cbm` | total, 3 desimal. Dari dimensi jika ada; jika tidak, CBM yang disebut |
| `kota_tujuan` | nama baku tingkat kota/kabupaten sesuai `data/referensi/kota.csv`. Kecamatan diganti kotanya (mis. Gubeng → Surabaya) |
| `jalur` | `laut`/`udara` hanya jika disebut |
| `info_kurang` | lihat di bawah |

## Info kurang

Info yang perlu ditanyakan supaya admin bisa memberi harga. Dihitung otomatis dari isian label
(`validator.aturan_info_kurang`), mengikuti cara kerja admin Pelita (sejak 27 Okt 2026):

- `jenis_barang` dan `kota_tujuan` jika tidak disebut.
- **Jumlah koli tidak pernah ditanyakan.** Ukuran atau berat total dianggap 1 koli, kecuali pelanggan
  sendiri menyebut ukuran per box dan jumlah box.
- Jalur `udara`: `berat` jika tidak ada, `branded` jika tidak disebut. Ukuran tidak wajib (hanya untuk cek
  berat volume).
- Jalur `laut`: `dimensi_atau_cbm` jika ukuran **dan** CBM sama-sama tidak ada.
- Jalur belum disebut: `jalur`, ditambah `berat` dan `dimensi_atau_cbm` hanya jika keduanya belum ada.

## Tag (`meta.tag`)

Dipakai untuk mengiris hasil evaluasi. Tambahkan tag baru di sini dulu.

| Tag | Arti |
|---|---|
| `revisi` | pelanggan mengoreksi nilai sebelumnya |
| `per_koli` | berat disebut per koli |
| `berat_total` | berat disebut untuk seluruh kiriman |
| `pcs_bukan_koli` | ada jumlah pcs yang bisa tertukar dengan koli |
| `satuan_jin` | berat dalam 斤 |
| `satuan_meter` | dimensi dalam meter |
| `satuan_tidak_tertulis` | dimensi tanpa satuan |
| `cbm_disebut` | pelanggan menyebut CBM/方/kubik |
| `kota_mandarin` | kota ditulis dalam Mandarin (泗水) |
| `kota_singkatan` | kota disingkat (jakbar, sby) |
| `campur_bahasa` | lebih dari satu bahasa dalam satu chat |
| `multi_grup` | lebih dari satu ukuran koli |
| `ada_gambar` | ada foto/PDF yang memuat info |
| `packing_list` | ada packing list |
| `kategori_perlu_dicek` | kategori belum bisa dipastikan; kolom kategori tidak dinilai |
| `perkiraan` | angka disebut sebagai perkiraan ("kurang lebih", "sekitar", "an") |
| `info_setelah_potong` | pelanggan memberi info tambahan setelah titik potong |
| `formulir` | pelanggan mengisi formulir "Nama saya / Rencana barang / Berat / Volume" |
| `pengandaian` | angka disebut sebagai pengandaian ("kalau misal aku pesen 0.1cbm") |
| `rentang` | angka berupa rentang ("10-20 kg"); kolomnya diisi `null` |
