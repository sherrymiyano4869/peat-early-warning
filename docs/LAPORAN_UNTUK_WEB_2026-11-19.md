# Laporan pembaruan lokal untuk web (2026-11-19)

Untuk: web, penulis kode webmap dan pipeline. Dari: sisi lokal (alat lokal di WSL, atas permintaan pemilik proyek).
Tujuan: memberi tahu apa yang sudah dipasang dan diubah di salinan lokal sejak v0.22, supaya zip berikutnya **tidak menimpa** perubahan itu, dan supaya sisa pekerjaan jelas.
Rincian desain per halaman ada di `docs/BRIEF_UIUX_REVISI.md` (bagian 1 sampai 8); laporan ini ringkasannya ditambah status.

## 1. Ringkasan

| Hal | Status |
|---|---|
| Zip web yang sudah dipasang | v0.23 (`peat-early-warning-v0.23.zip`, isinya masih berjudul v0.22) dan v0.24 (`peat-v0.24-patch.zip`), apa adanya. Tiga berkas uji lolos (`test_api`, `test_participatory`, `test_02f_ndmi`) |
| Perubahan lokal di luar zip | 6 commit sesudah v0.24; daftar di bagian 2 |
| Data | Tidak diperbarui sejak 2026-11-17 atas permintaan pemilik proyek; titik api berhenti di 2 Nov, stasiun sampai 16 Nov |
| Kobo | Formulir publik: `https://ee.kobotoolbox.org/x/zFYcDewv`. Pemilik proyek memilih **jalur B**: formulir Kobo tetap dipakai, halaman kita hanya mengantar |
| Hosting | Sedang disiapkan ke GitHub (repo `sherrymiyano4869/peat-early-warning`, publik) dan GitHub Pages untuk webmap statis; lihat bagian 5 |

Commit (lokal): v0.23 `825fe29`, v0.24 `aa8fb3b`; tambahan lokal `e924689`, `8ccdd71`, `25e4514`, `c110180`.

## 2. Berkas lokal yang perlu diadopsi atau dipertahankan

Zip berikutnya akan menimpa berkas yang sama. Mohon adopsi isinya ke sumber webmu, atau minta pemilik proyek memasangnya ulang.

| Berkas | Isi | Catatan |
|---|---|---|
| `webmap/about.html`, `webmap/team.html` | Terjemahan About dan Team dari mockup (`Downloads\Lomba\Lomba\desain-mockup`) dengan kelas v0.24 (`hero`, `sec`, `btn`) dan kelas baru `pg-*` | Peran dan deskripsi anggota tim kosong di sumbernya ("XXXX"); ditampilkan "belum diisi". Tombol "Get in Touch" diganti "Kenali Tim Kami" karena tidak ada email tim. Dua klaim About disesuaikan (tanpa "setiap hari" dan "menjelaskan alasannya") karena pipeline berjalan manual dan faktor pendorong belum diekspor |
| `webmap/lapor.html`, `webmap/lapor.js` | Halaman Lapor (jalur B): tombol ke formulir Kobo, 7 jenis laporan dari XLSForm, tingkat A/B/C, salin kode tugas dari `?tugas=T20261112-007` | Kode tugas hanya disalin, tidak terisi otomatis di dalam formulir |
| `webmap/pages.css` | Gaya halaman Tentang, Tim, Lapor; tombol emas `.nav-cta`; gaya kartografi Respons; popup besar | Dimuat setelah `style.css` di **semua** halaman |
| Bilah atas semua halaman (`index`, `monitoring`, `prediction`, `response`, `petugas`, `about`, `team`, `lapor`) | Tautan "Tentang", "Tim", dan tombol "Lapor" (`<a class="nav-cta" href="lapor.html">`); footer "Halaman" ikut | Satu `<link rel="stylesheet" href="pages.css">` ditambahkan di tiap `<head>` |
| `webmap/response.js` | Hanya gaya dan penyajian; **klasifikasi dan angka tidak berubah** (lihat bagian 3) | |
| `webmap/timeseries.js` | `num()` menampilkan bilangan bulat tanpa desimal ("0 hari", bukan "0,000 hari") | Perbaikan kecil |
| `serve_webmap.py` | Server statis tanpa cache peramban | Lokal; mengganti `python -m http.server`. Penyebabnya: peramban memakai `response.js` lama dari cache |
| `run_pipeline.sh`, `update_data.sh`, `PEMBARUAN.md` | Skrip dan dokumen lokal (bukan dari zip) | Jangan ditimpa atau dihapus |

## 3. Perubahan di `response.js` (agar bisa diadopsi)

1. Kategori punya `short` untuk legenda. Legenda memakai simbol bingkai putih yang mengikuti simbol peta (lingkaran saat jauh, sel saat dekat).
2. Pane Leaflet berurutan: prediksi < tugas < kejadian < penanda.
3. Kejadian: isi pekat (`fillOpacity` 0,88) dengan bingkai putih; zoom jauh (< 12) = `circleMarker` berukuran tetap (7, 9 untuk "keduanya"); zoom dekat = sel 1 km. Sorot saat disentuh. Laporan membara = satu-satunya penanda berdenyut (`prefers-reduced-motion` dihormati).
4. Tugas pemeriksaan **bukan lagi biru** (biru muda tertukar dengan kategori kejadian "Diperiksa, tidak ada kejadian" #56B4E9): tugas = **kotak** netral gelap (#2A1A14; belum = kotak kosong, sudah = kotak terisi; zoom dekat = sel dengan tint tipis atau pekat), kejadian = lingkaran berwarna. Beda bentuk dan beda isi, jadi aman juga untuk buta warna. Latar: dulu `fill:false` sehingga hanya garis tepi 2 px yang bisa ditekan, dan hilang saat zoom jauh. Kini zoom jauh = lingkaran padat; zoom dekat = sel berisi tint (belum = tipis, sudah = pekat), seluruh luas bisa ditekan. Popup besar (15 px) dengan tombol "Laporkan hasil pemeriksaan" ke `lapor.html?tugas=ID`. Alasan dan peluang tugas **tetap tidak ditampilkan** (pemeriksa buta).
5. Prediksi (`top_cells`) = wash ember lembut, bukan jaring garis hitam.
6. Kartu angka melayang di atas peta (`#kpi-strip`), dihitung dari `counters()` dan daftar tugas yang sudah ada.
7. Tampilan awal memusatkan sel tugas (area pilot) bukan seluruh Indonesia.
8. Peta dasar Respons dibuat pucat dan hangat lewat CSS (`body.fullmap .basemap-muted`); warna kategori bukti (Okabe-Ito) tidak diubah.

## 4. Permintaan ke web (berurutan menurut prioritas)

**A. Adopsi bagian 2 dan 3** ke sumber, supaya zip berikutnya membawanya.

**B. Respons masih memakai kontrol gaya lama**: dua radio, penggeser tanggal, `<select>` rentang, empat kotak centang. Samakan dengan pola mockup (tombol pil `aria-pressed`, kontrol segmen), sesuai `BRIEF_UIUX_REVISI.md` bagian 3. Panel kanan terlalu padat (tabel panjang).

**C. Cacat tampilan** (dari pemeriksaan v0.24):
1. Monitoring: ruang kosong di bawah kartu peta karena kolom kanan lebih panjang; nama stasiun panjang terbungkus empat baris dan tertimpa sparkline.
2. Beranda: kartu ke-4 di hero jatuh sendirian di baris kedua.
3. "Peta awal" dan ukuran `response.json` (lihat D3).

**D. Data dan model** (bukan masalah tampilan, tetapi terlihat jelas di tampilan baru):
1. **`14_fire_model`: peluang tidak konsisten.** Di `fire_cells.geojson` hanya 10 nilai `p1` unik dari 215 sel (lima teratas semuanya 0,571), dan 54 dari 215 sel punya `p3 < p1`, padahal "ada titik api dalam 3 hari" tidak mungkin lebih kecil daripada "besok". Daftar "Sel prioritas" jadi tidak informatif. Kemungkinan kalibrasi isotonik yang mendatar; mohon diperiksa dan dijamin monoton `p3 >= p1`.
2. **Tanda muka air terbalik** pada data SiTMAT 12 sampai 20 Agustus (13 dari 21 stasiun, contoh `MTI-AIF4R20B0UXP`: +61,28 pada 12 Agu, -30,2 pada 26 Sep). Mohon di `01`/`03`: deteksi titik balik tanda per stasiun, buang data sebelumnya, dan pastikan `wl_d3`, `wl_d7`, dan target 7/14 hari tidak menyeberangi titik itu. Zip terakhir belum menyebutnya.
3. **`webmap/data/response.json` berukuran 55 MB.** Terlalu berat untuk situs publik dan mendekati batas GitHub (peringatan di 50 MB, ditolak di 100 MB). Mohon dipangkas (hanya sel area pilot dan rentang yang dipakai halaman, atau dipecah per bulan).
4. Pengeringan per sel masih "belum teruji" (jumlah uji 0, ditulis "cakupan 0%"); mohon lencananya menulis "belum teruji", bukan 0%.
5. Titik api dan prediksi titik api tertinggal (2 Nov); kartu "652 hari ini" sebaiknya menulis tanggalnya.

**E. Lapor dan Petugas:**
1. Bila memungkinkan, isi otomatis "Kode tugas pemeriksaan" di formulir Kobo lewat parameter Enketo (butuh nama simpul formulir yang belum diketahui sisi lokal).
2. Tautkan tiap tugas di `petugas.html` ke `lapor.html?tugas=ID`.
3. Halaman **Publik** (cari desa, status, ramalan 7 hari, lapor) belum ada. Batas desa 1:10.000 dari BIG sudah tersedia di `Downloads\Lomba` (83.518 poligon; 210 di area pilot); perlu dipotong dulu.

**F. GitHub Pages** (bagian 5): semua jalur harus relatif; `api.js` sudah punya cadangan cermin statis; Petugas berjalan mode demo tanpa server API. Mohon tidak menambahkan ketergantungan pada server di halaman publik.

## 5. Hosting ke GitHub (rencana, belum dijalankan)

* Repo `github.com/sherrymiyano4869/peat-early-warning` sudah ada dan publik. `main` lokal 8 commit di depan dan 1 commit di belakang (revisi `PEMBARUAN.md` dari GitHub).
* Kode ke `main`; webmap ke GitHub Pages lewat cabang `gh-pages` yang dibuat `publish_pages.sh` (`data/` webmap diabaikan git, jadi tidak ikut `main`).
* Syarat atribusi di situs publik: OpenStreetMap (ODbL, peta dasar dan kanal), FABDEM (CC BY-NC-SA, hillshade), BRGM BlueBook, ESA WorldCover, NASA FIRMS. Mohon halaman "Atribusi dan penafian" memuat semuanya.

## 6. Yang tidak boleh berubah

1. Tugas pemeriksaan tetap membuat pemeriksa **buta** terhadap alasan dan peluang (desain 18/19).
2. Tidak ada status wilayah satu tingkat (Aman sampai Darurat) tanpa aturan tervalidasi; tidak ada angka ilustrasi; lencana kepercayaan model tetap tampil.
3. `config.yaml` dan `data/` tidak disentuh; token (Kobo, FIRMS) tidak pernah ditulis ke berkas.
4. Titik laporan dan kode pelapor tidak diekspor ke web; hanya sel 1 km.

## 7. Cara memeriksa

1. `python serve_webmap.py`, buka `http://localhost:8000` (jangan lewat `file://`).
2. Setiap halaman memuat `pages.css`, punya tautan "Tentang", "Tim", dan tombol "Lapor", dan tidak ada galat di Console.
3. Respons: zoom jauh menampilkan lingkaran, zoom dekat menampilkan sel; menekan di dalam sel tugas membuka popup; tombol di popup membuka `lapor.html` dengan kode tugas.
4. `fire_cells.geojson`: `p3 >= p1` di semua sel dan jumlah nilai `p1` unik jauh lebih banyak dari 10.
