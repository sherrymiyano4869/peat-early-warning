# Catatan desain dan daftar revisi (AGC 2027, peringatan dini kekeringan gambut)

Dokumen hidup: tambahkan tanggal tiap kali ada keputusan. Ditulis 10 Nov 2026 (v0.16), diperbarui 11 Nov 2026 (v0.17, tinjauan kartografi).

## 1. Keputusan yang sudah diambil
**Struktur sistem.** Dua sistem yang saling memvalidasi, bukan terpisah:
- Pemantauan dan prediksi: data statis (topografi, kanal, LULC, batas gambut dan KHG) dan dinamis (hujan, citra, ENSO dan IOD, stasiun SiTMAT)
  disatukan di kubus data grid; cabang "Saat ini" dan cabang "Prediksi".
- Respons dan penilaian: ToPeCAl-2 (Sentinel-2), VIIRS, dan laporan warga/BPBD dicocokkan ruang-waktu di buku besar kejadian.
- Umpan balik dari respons ke prediksi: catatan tindakan (jadi fitur), pantauan sisa (penanda sel), label terverifikasi (hanya untuk menilai).

**Tampilan web.** Dua tab: "Saat ini" (semua parameter penyusun: hujan, ENSO, topografi, citra, kanal garis, LULC, stasiun) dan "Prediksi" (hanya peta
kerawanan). Tab Respons terpisah, hotspot belum diintegrasikan.

**Peta kerawanan = tiga lapis:** (1) indeks relatif seamless, (2) kalibrasi stasiun hanya di dalam AOA, (3) kepercayaan selalu tampil
(transparansi dan arsiran). Keterangan wajib: "indeks relatif, bukan peluang kebakaran".

**Penyajian tiga tingkat (generalisasi per skala):** zoom jauh = satu poligon per KHG; zoom menengah = sel 500 m; zoom dekat = sel 100 m (hanya pilot).
Pilot Jambi dulu; seluruh wilayah (gambut Sumatra dan Kalimantan) pada 250-500 m menyusul.

**Sumber data.** LULC: ESA WorldCover 10 m v200 (2021, CC BY 4.0; tidak ada kelas sawit, potret 2021). Batas gambut dan KHG: BRGM BlueBook (cek izin pakai,
cantumkan atribusi). DTM: FABDEM (CC BY-NC-SA 4.0). Hujan: GSMaP (CHIRPS pembanding; CHIRPS di GEE tertinggal sekitar 5 minggu).

**Kartografi.** Palet YlOrRd 5 kelas khusus kerawanan; kanal sebagai garis biru tipis (BUKAN peta panas, karena terbaca sebagai hotspot); batas KHG garis gelap
putus-putus; batas kabupaten abu tipis; peta dasar abu muda; skala dan arah utara; legenda dengan satuan dan tanggal data.

**Alur ToPeCAl-2 (sudah dicocokkan dengan paper Sofan dkk. 2020):** masker (awan, air, benda terang tetap) -> SICI = SWIR-2/SWIR-1 > 1 -> ambang SWIR-2 berbeda
untuk atmosfer jernih dan berasap (penentu: pita biru) -> tes kontekstual (jendela 61x61 piksel) hanya untuk kandidat membara dan campuran; cloud mask adalah varian
alternatif. Akurasi di paper: menyala jelas di atas 95%, membara hanya 35% (kontekstual) dan 56% (cloud mask) benar -> "kandidat membara" tidak boleh disajikan pasti.

**Pencocokan.** Radius sekitar 1 km dan jendela 24-48 jam adalah ANGKA AWAL (tanpa sumber), disetel dengan data sekunder BPBD.

**Keputusan kartografi (tinjauan 11 Nov 2026, v0.17).** Pesan peta: indeks relatif kerentanan gambut terhadap pengeringan; satu peta, satu pesan.
- Grid pada zoom jauh dipertahankan, TANPA goresan abu-abu (isi berwarna saja; garis sewarna isi mencegah celah halus antarpoligon).
- Stasiun: satu simbol, bukan dua mode. Warna = kelas muka air terakhir dengan titik tengah divergen di ambang -40 cm (biru = di atas ambang;
  pasir, cokelat, cokelat tua = makin dalam), abu-abu = tanpa data, abu-abu berongga putus-putus = berhenti melapor lebih dari 3 hari. Peluang turun TIDAK lagi
  mewarnai penanda (angkanya belum terbukti lebih baik daripada persistensi); tampil di popup berbahasa jelas dengan peringatan bila validasi belum ada.
- Relief lokal diganti hillshade dari FABDEM 30 m (sinar barat laut, relief diperbesar, kontras diregangkan otomatis, di bawah kerawanan). Peringatan: kesalahan
  vertikal FABDEM di hutan tropis sebanding dengan relief kubah; sebagian tekstur halus bisa artefak.
- "Di luar AOA" dan "jarak ke stasiun" dihapus dari antarmuka (istilah teknis, informasinya sudah dibawa transparansi dan arsiran kepercayaan, ditambah penjelasan
  di legenda). Masih tersedia untuk analis lewat `09_export_web.py --advanced-layers`.
- Legenda dipindah ke kotak di peta (bukan hanya di panel); memuat kelas, skema kelas (kuintil acuan tetap, kelas relatif), kepercayaan, dan "tanpa warna = tidak dinilai".
- Angka di popup memakai format Indonesia (koma desimal) dan satuan; kontrol "Transparansi" diganti "Opasitas" dengan keterangan arah.
- Verifikasi (protokol skill kartografi): simulasi buta warna (protan, deutan, tritan; Machado 2009) selisih warna antar-kelas bertetangga terkecil 13,1 dE untuk palet kerawanan
  dan 28,8 dE untuk palet stasiun; kelas terendah kerawanan terhadap peta dasar CARTO Positron 37 dE (31,7 dE pada opasitas 0,85). Pada kepercayaan rendah (opasitas 0,59) kelas
  sengaja lebih sulit dibedakan. Sumber palet: ColorBrewer (registri skill terakhir diverifikasi 19 Jul 2026, diperiksa 11 Nov 2026).
- Belum: histogram dengan batas kelas di alur kerja, uji dua skema kelas (kuintil vs batas manual) untuk melihat apakah cerita berubah, peta statis (matplotlib, palet
  sama) untuk slide, tata letak panel di layar ponsel, pemotongan raster mengikuti batas gambut BlueBook asli.

**Peta dasar (11 Nov 2026).** OpenStreetMap standar (tanpa kunci API), diredam dengan filter CSS agar tidak mengalahkan tema. Kebijakan tile OSM: pemakaian berat dilarang tanpa izin
dan atribusi wajib jelas; browser biasa sudah mengirim Referer dan User-Agent yang dibutuhkan. URL peta dasar bisa diganti lewat `webmap.basemap` di config.yaml
(masuk manifest) tanpa mengubah kode, bila lalu lintas besar (server tile sendiri atau penyedia berbasis OSM).
Catatan: WebGIS HARUS dibuka lewat server (`python -m http.server -d webmap 8000`, lalu http://localhost:8000). Dari file:// OSM menjawab 403 karena tidak ada Referer.
Bila masih 403 di localhost, periksa ekstensi privasi atau perisai peramban yang membuang Referer, atau ganti peta dasar lewat `webmap.basemap`.

**Usulan arsitektur data dan alur kerja (menunggu keputusan; 11 Nov 2026).** Dua segmen: Monitoring (kini) dan Predicting (masa depan, LightGBM).
- SiTMAT adalah ACUAN (kalibrasi dan validasi indeks), bukan bahan indeks. Bahan dinamis: defisit hujan dan hari tanpa hujan (GSMaP), indeks kelembapan tanah, anomali NDMI/S1.
  Bahan struktural: kanal, relief, LULC. Titik api teramati (VIIRS) ditampilkan di Monitoring tetapi TIDAK masuk indeks (hasil, bukan bahan; jaga agar tidak melingkar).
- Predicting titik api = peluang per sel (bukan titik pasti), target berbeda dari kekeringan: dipicu manusia, label VIIRS jarang dan bias awan/asap. Wajib dibandingkan dengan dasar
  (klimatologi sel-bulan, titik api kemarin, HTH/KBDI) dengan PR-AUC, skill Brier, kurva keandalan, dan tangkapan pada sel teratas.
- Lapisan data: L0 mentah bertanggal (tak ditimpa, manifest sumber dan lisensi), L1 sel-hari terstandar (GeoParquet, COG), L2 tabel fitur (Parquet per tanggal), L3 produk, L4 arsip
  prediksi dan kejadian (tak berubah). Satu grid induk bersarang (100 m, 500 m, 1 km) dalam satu CRS (cross-region: EPSG:6933; pilot masih UTM 32748, putuskan migrasi sebelum tahap wilayah).
- Harian: ambil -> cek mutu -> seragamkan -> fitur -> monitoring -> prediksi -> arsip -> ekspor web. Mingguan: skor prospektif -> uji lebih baik dari dasar -> latih ulang atau batasi kepercayaan.
- Sumber: VIIRS 375 m arsip FIRMS sejak 20 Jan 2012 (perlu akun Earthdata); NRT diganti data sains dengan jeda beberapa bulan, jadi catat jenis data di manifest (pergeseran latih-layani);
  koleksi Earth Engine NASA/LANCE/SNPP_VIIRS/C2 hanya sejak 3 Sep 2023, jangan jadi satu-satunya sumber latih.

**Keputusan 11 Nov 2026 (lanjutan, v0.18).**
- Sel titik api: 1 km. CRS grid induk dipindah SEKARANG ke ESRI:54034 (equal-area, paralel standar 0), KOREKSI atas saranku semula (EPSG:6933): di ekuator 6933 membuat sel
  "1 km" menjadi 1,15 x 0,87 km di tanah. Peta web tetap sejajar dengan OSM karena tile selalu diproyeksikan ke Web Mercator (diuji: selisih 1 m pada z14).
- Dua halaman: Monitoring = kondisi kini (indeks kerentanan struktural dan, nanti, tekanan dinamis; titik api teramati; muka air stasiun), berhenti di "kondisi kini", bukan kerawanan masa depan.
  Prediksi = kerawanan ke depan: peluang titik api 1-3 hari (LightGBM), prakiraan muka air stasiun 7-14 hari, dengan status bukti. Peta kerentanan struktural menjadi lapisan dasar kedua halaman.
- Titik api = peluang per sel dengan gerbang bukti; hasil prospektif (arsip) menentukan klaim. Hasil pada data tiruan (PR-AUC model 0,27 lawan persistensi 0,20 dan klimatologi 0,005 pada h1)
  hanya menguji alur, BUKAN bukti kinerja. Klimatologi bisa ber-ROC-AUC di bawah 0,5 secara gabungan bila waktu musim uji berbeda dari tahun-tahun latih.
- Kunci: FIRMS memakai MAP_KEY (email cukup). Kata sandi Earthdata TIDAK dipakai kode dan tidak boleh ditempel di obrolan atau berkas; ganti kata sandi yang sudah terlanjur dibagikan.
- Ditambahkan (v0.19, 11 Nov 2026): sumber kelembapan tanah diputuskan ERA5-Land (ECMWF/ERA5_LAND/DAILY_AGGR, lapisan 0-7 cm; reanalisis model dengan hidrologi tanah mineral umum, BUKAN pengamatan dan
  tidak memodelkan gambut; tanggal akhir ketersediaan di Earth Engine berubah-ubah, skrip memotong sampai tanggal terakhir). Hujan GSMaP per piksel 0,1 derajat; NDMI komposit bulanan per sel; WorldCover
  (tanpa kelas sawit); ENSO/IOD harian regional (bulan sebelumnya); model pengeringan per sel (15) dengan uji ruang-waktu. Semua bagian Earth Engine (02e, 02f) BELUM diuji terhadap Earth Engine sungguhan.
- Prinsip konsistensi: fitur sel stasiun dan sel peta berasal dari kubus yang sama (statis 1 km, hujan/tanah per piksel produk, NDMI komposit), bukan dari fitur titik stasiun (02). Anomali kausal (hanya tahun
  sebelumnya, min. 3 tahun): tahun awal rekaman tanpa anomali.
- Masih belum: hotspot ToPeCAl-2, penilaian prospektif otomatis, Sentinel-1 per sel (VV), sumber kelembapan tanah alternatif (SMAP) untuk pembanding, tabel hujan CHIRPS per sel (CHIRPS tertinggal ~5 minggu),
  pelatihan wilayah besar (kubus memuat semua tanggal ke memori; pilot saja).

## 2. Daftar revisi diagram (dari tinjauan 10 Nov 2026), urut prioritas
1. Tambah langkah "nilai prediksi vs kejadian" yang menghasilkan skor validasi dan masuk ke "Hitung kepercayaan" (batas skill). Sekarang panah umpan balik hanya ke "Tandai pantauan sisa".
2. "Verifikasi" perlu dua keluaran: ya (lanjut tindakan), tidak (alarm palsu -> label negatif, tutup). Bedakan "verifikasi" (kejadian) dan "validasi prediksi" (model).
3. ToPeCAl-2: masking juga menyebut awan; tambah tes kontekstual atau cloud mask untuk kandidat membara.
4. Tambah pilihan "Keyakinan cukup?" sebelum tiga kemungkinan (jalur tidak = tunggu data baru).
5. Penamaan: satu istilah (keyakinan = skor kejadian, kepercayaan = keandalan peta); "terkni" -> "terkini"; "threshold bobot confidence" -> "beri bobot keyakinan";
   "groundwater model SiTMAT" -> "stasiun muka air SiTMAT"; "rainfall CHIRPS" -> "GSMaP (CHIRPS pembanding)"; "ENSO NOAA" -> "ENSO dan IOD (DMI)";
   "DTM copernicus" -> "DTM (FABDEM)"; "Peringatan" -> "notifikasi tindakan (prototipe)".
6. Satu keputusan desain: sensor virtual -> prakiraan? Saat ini dibiarkan terpisah (sensor virtual per sel masih lemah).

## 3. Jebakan yang harus dijaga (bukan hanya teknis)
- Paradoks keberhasilan peringatan: peringatan yang berhasil mencegah kebakaran membuat model tampak salah. Catat tindakan dan nilai sel bertindakan terpisah.
- Bias verifikasi: sel berisiko tinggi lebih sering diverifikasi. Sisihkan verifikasi acak kecil di sel berisiko rendah.
- Kejadian yang masuk ke kerawanan hanya yang diketahui SEBELUM tanggal terbit; penilaian memakai kejadian sesudahnya (hindari kebocoran).
- LOSO terlalu optimis untuk prakiraan; percayai LOCO, LOIO, dan TEMPORAL. Skill model belum terbukti melampaui persistensi sampai walk-forward menunjukkannya.
- Indeks kerawanan: arah dan bobot komponen adalah asumsi; uji kepekaan dan tulis di metode. Kelas memakai ambang acuan tetap (reference_quantiles.json), bukan persentil
  minggu itu.

## 4. Status pengerjaan (v0.16)
Sudah ada: prototipe tiga tingkat di webmap (08 indeks struktural, 10 tile dan unit, tampilan zoom, kepercayaan sebagai transparansi dan arsiran, kanal garis,
skala, arah utara); diuji pada data tiruan dan simulasi peramban (node), belum di peramban sungguhan dan belum dengan data Jambi asli.
Belum ada: tekanan dinamis per sel (hujan, NDMI, HTH, ENSO), ekstraksi WorldCover, batas gambut/KHG/administrasi asli dari BlueBook, kalibrasi stasiun per sel,
pemilih kotak pilot, tab Saat ini dan Prediksi terpadu penuh, mode inkremental 02, orkestrator, penilaian prospektif (10_score_archive), ToPeCAl-2, VIIRS, buku besar kejadian.

## 5. Pertanyaan terbuka
- Sumber batas administrasi: BlueBook atau terbuka (geoBoundaries; periksa lisensi).
- Respons di web: hanya menampilkan (laporan, validasi, pelabelan lewat KoboToolbox) atau backend kecil? Usulan: hanya menampilkan untuk lomba.
- Definisi kerawanan final: kerawanan kekeringan (disarankan sebagai target) dengan kebakaran sebagai bukti validasi, atau kerawanan kebakaran.
- Bobot komponen indeks dan uji kepekaannya; apakah LULC diberi bobot (bawaan 0).

## 6. Urutan kerja
Aktif: nomor 1 (sistem prediksi dan WebGIS terpadu): definisi -> lapisan data -> model/indeks per sel -> dashboard terpadu -> uji.
Nanti: nomor 2 (model respons dan penilaian yang dapat memengaruhi model saat ada laporan). **Ingatkan setelah nomor 1 selesai.**

## 7. Menjalankan prototipe tiga tingkat
    python scripts/07_grid_static.py
    python scripts/08_susceptibility.py --peat-gpkg data/raw/batas/gambut.gpkg --peat-layer NAMA
    python scripts/10_build_tiles.py --units-gpkg data/raw/batas/khg.gpkg --units-layer NAMA --units-name KOLOM_NAMA \
        --canal-gpkg data/raw/kanal/kanal_osm_clip.gpkg --canal-layer kanal_pilot_klaster5
    python scripts/09_export_web.py
    python -m http.server -d webmap 8000        # buka http://localhost:8000
Tanpa --units-gpkg, tingkat 1 memakai blok 5 km (sementara). Rentang zoom bawaan: unit 0-10, kasar 11-12 (tile z9-12), halus 13-18 (tile z13-15).
Ukuran pada data tiruan pilot sekitar 55x60 km: sekitar 3.100 tile halus dan 75 tile kasar, 7,7 MB, 46 detik.
