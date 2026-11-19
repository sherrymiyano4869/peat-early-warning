# Brief revisi UI/UX webmap: samakan kontrol dengan mockup, bukan hanya warna

Untuk: web (penulis kode webmap). Dibuat 2026-11-19 dari pemeriksaan folder `Downloads\Lomba` dan webmap v0.23 yang terpasang.

## 1. Keluhan

Di v0.23 yang ditiru dari mockup hanya **kulitnya**: warna Ember and Sand, font Space Grotesk dan Inter, bilah atas, kartu beranda.
**Kontrolnya masih gaya lama.** Halaman Monitoring, Prediksi, dan Respons tetap memakai:

| Halaman | Kontrol sekarang (v0.23) |
|---|---|
| Monitoring | 7 kotak centang (kerentanan, hillshade, titik api, KHG, admin, kanal, stasiun) + penggeser opasitas + tulisan "Tingkat tampilan: per blok 5 km" + `<details>` atribusi, semua dalam satu panel kanan yang panjang |
| Prediksi | 3 tombol radio (tema) + 5 kotak centang + penggeser opasitas + 3 lencana berteks panjang; **tidak ada pemilih horizon** |
| Respons | 2 tombol radio (mode) + penggeser tanggal + `<select>` rentang + 4 kotak centang |

Halaman Petugas sudah mengikuti mockup (tombol pil `aria-pressed`, lembar status). Pola itulah yang diminta untuk tiga halaman di atas.

## 2. Isi folder `Downloads\Lomba` (hasil pemeriksaan)

| Bagian | Isi | Catatan |
|---|---|---|
| `desain-mockup/` (144 KB) | 8 halaman mockup `.dc.html` + `canvas.json`: Home, Main (Overview), Prediksi, About, Team, Petugas (ponsel 390 px), Publik (ponsel 390 px), Palette | Berkas `support.js` yang dirujuk tidak ikut, jadi tidak bisa dibuka mandiri; dibaca sebagai sumber. Angka di dalamnya **ilustrasi**, tertulis "not real data". Dibuat 2026-11-18 |
| `_publish/project/` | Salinan **identik byte-per-byte** dari `desain-mockup/` | Abaikan |
| `peat-early-warning-main/` (1,2 MB) | Salinan repo tanpa data, versi **v0.22** | Lebih tua dari yang terpasang: tidak punya `api.js`, `petugas.*`, atau gaya Ember. **Jangan dijadikan dasar** |
| `BATAS WILAYAH KELURAHAN-DESA 10K/` (1,3 GB) | Shapefile batas desa/kelurahan skala 1:10.000 dari BIG (metadata 2023): 83.518 poligon se-Indonesia, EPSG:4326, kolom `NAMOBJ`, `WADMKD` (desa), `WADMKC` (kecamatan), `WADMKK` (kabupaten), `WADMPR` (provinsi), `KDEPUM` (kode desa), `LUAS` | 210 desa menutupi kotak pilot. Tanpa indeks spasial, membacanya per kotak butuh sekitar 2,5 menit. Lapisan ini yang dibutuhkan halaman Publik (cari desa) dan lapisan batas admin |

## 3. Yang diminta: pola kontrol dari mockup

Terjemahkan **perilaku kontrol dan susunan halaman**, bukan hanya warna. Id elemen yang dipakai `app.js`, `response.js`, `timeseries.js` boleh diubah asal JS-nya ikut diperbarui dan diuji.

### Monitoring (padanan `Main.dc.html`)
1. Lapisan peta: **tombol pil** (`aria-pressed`, tinggi minimal 44 px; aktif = isi merah-bata, tidak aktif = putih bergaris) untuk *Kerentanan*, *Titik api 7 hari*, *Stasiun*, *Kanal*. Hillshade, batas KHG, batas admin, dan opasitas dipindah ke satu panel "Lanjutan" yang tertutup. Tidak ada lagi kotak centang di panel utama.
2. Panel samping diganti **kartu terpisah di bawah peta** (bukan satu kolom panjang): kartu angka (sudah ada; tambahkan tren "dibanding minggu lalu" bila dapat dihitung dari deret yang ada), daftar **Sel prioritas besok** (urut dari `fire_cells.geojson`: peringkat, id sel, peluang `p1`; klik = peta bergeser ke sel), kartu **muka air per stasiun** dengan sparkline (dari `series/*.json`; stasiun di bawah −40 cm ditandai), deret waktu yang sudah ada, dan daftar **laporan lapangan terbaru** dari `response.json` (hanya sel 1 km dan tingkat bukti A/B/C; tidak ada titik laporan atau kode pelapor).
3. Buang tulisan teknis dari muka panel ("Tingkat tampilan: per blok 5 km", paragraf legenda panjang). Pindahkan ke tooltip atau "Tentang peta ini".
4. Pemilih wilayah (`<select>`) di bilah atas seperti mockup, walau baru berisi satu pilihan ("Pilot: pesisir Jambi").

### Prediksi (padanan `Prediksi.dc.html`)
1. **Dua kontrol segmen** (pil dalam wadah krem, satu aktif): *Tema* (Peluang titik api | Pengeringan muka air) dan *Horizon*. Horizon mengikuti tema: titik api = Besok / 3 hari (`p1`, `p3`); pengeringan = 7 hari / 14 hari (`p7`, `p14`). Data keduanya sudah ada di `fire_cells.geojson` dan `dry_cells.geojson`.
2. Klik sel membuka **panel detail** (bukan popup Leaflet): id sel, peluang untuk horizon terpilih, lalu faktor pendorong sebagai batang bila nilai per sel memang diekspor (hari tanpa hujan, NDMI, jarak ke kanal, ENSO). Jika nilai per sel belum diekspor, minta ekspor dari 14/15; **jangan mengarang panjang batang**.
3. Kartu **"Seberapa jauh model bisa dipercaya?"** dari metrik nyata (`fire_metrics.json`, `dryness_metrics.json`, `walkforward_summary.csv`); grafik kalibrasi hanya bila data keandalannya diekspor.
4. Tiga lencana teks panjang diringkas menjadi satu baris status per model yang bisa dibuka rinciannya.

### Respons
Mode (Hanya satelit | Satelit + laporan lapangan) menjadi kontrol segmen; empat lapisan menjadi tombol pil; rentang tanggal (7 / 14 / 30 hari / semua) menjadi kontrol segmen alih-alih `<select>`; penggeser tanggal boleh tetap, tetapi diberi gaya yang sama.

### Halaman yang belum ada
* **Publik (ponsel)**: cari desa, status satu tingkat untuk desa itu, ramalan 7 hari, saran tindakan, tombol "Lapor asap/api". Butuh poligon desa dari shapefile di atas (potong dulu ke Jambi atau kotak pilot, simpan sebagai `data/raw/batas/desa.gpkg`).
* **About** dan **Team**: halaman statis; teksnya ada di mockup.

## 4. Jangan dibawa dari mockup (bertentangan dengan keputusan proyek)

1. **Angka ilustrasi.** "ALERT", "14 sel", "3 dari 12 stasiun", kurva kalibrasi yang "dekat garis ideal", semuanya contoh. Semua nilai harus dari berkas keluaran, dengan tanggal data dan status bukti yang sudah ada.
2. **Status wilayah / desa satu tingkat (Aman, Siaga, Bahaya, Darurat; di mockup SAFE/CAUTION/ALERT/DANGER).** Belum ada aturan tervalidasi yang menurunkannya. Itu sebabnya v0.22 sengaja tidak punya kartu status regional. Kalau halaman Publik butuh tingkat, turunkan dari indeks relatif yang ada, beri label "indeks relatif", dan tulis aturannya di dokumen. Jangan menampilkannya sebagai peringatan resmi.
3. **Lencana model.** Model titik api unggul atas klimatologi dan hanya tipis atas persistensi pada uji retrospektif (PR-AUC 0,16 lawan 0,01 dan 0,13), belum diuji prospektif; pengeringan per sel belum teruji sama sekali (jumlah uji 0); prakiraan muka air stasiun belum mengalahkan persistensi (skill −0,04). Gaya baru **tidak boleh** membuat hasil ini terlihat lebih meyakinkan: lencana kepercayaan tetap tampil, dan sel dengan kepercayaan rendah tetap dipucatkan.
4. **Petugas melihat "Highest probability" dan persentase peluang per tugas** (mockup). Itu membuka pemeriksa terhadap alasan tugas. Desain 19/18 membuatnya buta (tugas teratas, acak, dan pantauan sisa tidak dibedakan) agar skor prospektif tidak bias. Pertahankan tampilan yang sekarang.
5. **Tombol "Buat tugas pemeriksaan" manual di detail sel.** Tugas dibuat oleh 19 (teratas + acak + sisa). Tugas manual bisa merusak skor 18. Bila tetap diinginkan, jenisnya harus tersendiri dan dikeluarkan dari skor.
6. **Tombol tanpa fungsi** ("Download Report (PDF)", "Cell History", "Get in Touch"): jangan tampil sebagai tombol aktif. Buat berfungsi, atau sembunyikan, atau beri keterangan "belum tersedia".

## 5. Ketentuan teknis

* Situs tetap statis (Leaflet, tanpa langkah build), jalan lewat `python -m http.server -d webmap`; font punya cadangan sistem tanpa internet.
* Tinggi target sentuh minimal 44 px; `aria-pressed` untuk tombol toggle; bisa dioperasikan dengan papan ketik; layar 390 px memakai lembar bawah.
* Data dari `manifest.json` dan `webmap/api.js` (API v1 atau cermin statis `data/v1`); jangan menghitung angka baru di peramban.
* Pertahankan `timeseries.js`, `09b_export_timeseries.py`, dan perbaikan file:// dari v0.17.2.
* `config.yaml` dan `data/` tidak disentuh. Sertakan catatan perubahan, dan jelaskan elemen mana yang berganti id.

## 6. Cara memeriksa hasilnya

1. Tangkapan layar Monitoring dan Prediksi pada lebar 1440 px dan 390 px. Tidak boleh ada `<input type="checkbox|radio">` bawaan peramban pada kontrol utama.
2. Pindah tema dan horizon di Prediksi: legenda, peta, dan ringkasan ikut berganti, nilainya sama dengan berkas sumber.
3. Klik satu sel di daftar prioritas dan satu sel di peta: panel detail memuat angka yang sama dengan `fire_cells.geojson`.
4. Cek tiap poin di bagian 4 dengan membaca kode, bukan hanya melihat tampilannya.
