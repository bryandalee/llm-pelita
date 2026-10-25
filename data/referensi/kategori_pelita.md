# Kategori tarif Pelita (dari admin, 25 Okt 2026)

Dipakai untuk mengajari model memilih `kategori_barang` (tarif laut) dan `branded` (tarif udara),
lewat prompt v7. Sumber: penjelasan admin, tabel riwayat kiriman pelanggan, dan tabel garmen vs semi
garmen dari admin. Harga sengaja tidak ditulis. Contoh yang sama persis dengan kiriman di chat test
tidak dimasukkan (filter air), supaya evaluasi tetap jujur.

## Tarif laut

Batas lartas ringan dan lartas berat kadang samar, karena mengikuti peraturan impor barang dari China.

| Kategori | Aturan | Contoh |
|---|---|---|
| tas | tas, dompet, koper, ransel (bukan dari kain) | tas, dompet, koper, ransel |
| umum | barang umum biasa | sepatu, seed dressing, buku stiker |
| lartas ringan | barang larangan/pembatasan impor (ringan) | printer consumables, barang/aksesori mobil, botol plastik |
| lartas berat | barang larangan/pembatasan impor (berat) | aki (baterai aki), shield |
| semi garmen | aksesori pakaian dan bahan tekstil; regulasi lebih longgar daripada garmen | kaos kaki, sarung tangan, topi, hijab/jilbab, dasi, syal, sapu tangan; tas kain, dompet kain, sabuk kain; kain gulungan, benang, ritsleting |
| garmen | pakaian jadi utuh; paling ketat di bea cukai | baju, kaos, celana, jaket, dress, rok, pakaian dalam |

Jika barang tidak ada di tabel: pilih kategori yang paling mirip (admin akan mengonfirmasi).

## Tarif udara: branded vs non-branded

Setiap barang udara masuk salah satu:
- **branded**: barang bermerek **internasional** (Nike, Adidas, Pokemon, dll.), **termasuk KW/replika**.
  Contoh: sepatu merek internasional, tas bermerek, kartu Pokemon.
- **non-branded**: tanpa merek, atau merek kecil/lokal. Contoh: barang/aksesori mobil, baju tanpa merek.

## Barang khusus

- **Baterai isi ulang** seperti baterai HP/laptop (lithium) **tidak bisa dikirim**, baik udara maupun
  laut, karena bisa meledak. Baterai **aki** bisa via laut (lartas berat).
- **Cairan tidak bisa via udara** (hanya laut).
- Sebagian barang hanya bisa via laut atau perlu dicek tim lapangan dulu (mis. alat kesehatan, lem).
