# Changelog

## v0.21
- Halaman Respons (webmap/response.html + response.js, data dari scripts/20_export_response.py): sel 1 km berwarna menurut sumber bukti (satelit, laporan, keduanya, nihil,
  belum terverifikasi), penanda laporan membara, saklar "Hanya satelit" lawan "Satelit + laporan" dengan tabel sebelum dan sesudah, penggeser rentang waktu, tugas pemeriksaan
  terbitan terakhir, sel berpeluang tertinggi, sekat, muka air lapangan, dan panel "Apakah prediksi terbukti?" dari 18. Lencana merah bila ada laporan tiruan
- Privasi: response.json tidak memuat titik laporan kejadian, kode pelapor, atau alasan tugas (diuji di tests/test_participatory.py)
- Tautan Respons ditambahkan ke navigasi Monitoring, Prediksi, dan Beranda; app.js tidak diubah
- Diuji di Chromium tanpa akses internet: peta dasar OSM BELUM terlihat pada uji; periksa di perambanmu

## v0.20
- Data partisipatif yang terkait dengan prediksi (sistem nomor 2 di catatan desain, dimajukan):
  src/reports.py (skema tunggal), tools/build_xlsform.py -> forms/laporan_lapangan.xlsx (lolos konversi pyxform), tools/fake_reports.py (laporan TIRUAN)
- scripts/19_verification_tasks.py: tugas pemeriksaan dari fire_prob_latest (teratas, acak dengan peluang terpilih, pantauan sisa); berkas pemeriksa tanpa alasan dan peluang
- scripts/16_ingest_reports.py: Kobo (api/v2, token dari KOBO_TOKEN) atau CSV -> L0 bertanggal dengan sha256, identitas dibuang sebelum disimpan -> reports.parquet; GPS buruk dan
  laporan terlambat ditandai, tidak dibuang
- scripts/17_event_ledger.py: buku besar sel-hari (laporan + VIIRS; radius 1 km dan 48 jam masih ANGKA AWAL), tingkat A/B/C, nihil, konflik, catatan upaya (n_kunjungan),
  label y_viirs / y_buku / y_lapangan, kondisi sekat terakhir per titik (belum dipakai 08)
- scripts/18_score_prospective.py: nilai arsip fire_prob terhadap kejadian sesudah tanggal terbit (tiga definisi kenyataan, dengan dan tanpa sel bertindakan), laju kejadian tugas
  teratas lawan acak (Fisher), Spearman indeks kerentanan lawan muka air lapangan per titik
- tests/test_participatory.py: dunia tiruan di folder sementara; aturan tingkat, pembuangan baris rusak, jendela lengkap, dan hitungan positif diperiksa terhadap hitungan mandiri
- Belum: server Kobo sungguhan, data laporan nyata, sekat kanal masuk 08, laporan sebagai fitur 14, tampilan Respons di webmap, lolos_prospektif belum menaikkan kelas kepercayaan

## v0.19.1
- 02f NDMI: perbaikan galat Earth Engine "Image.reduceResolution: The input to reduceResolution does not have a valid default projection". Komposit median() tidak punya proyeksi tetap;
  kini ditetapkan setDefaultProjection (EPSG:4326, 20 m) sebelum reduceResolution, dengan cadangan proyeksi asli B11 bila server menolak. Piksel tertutup awan diberi NODATA (-9999) dan
  dikeluarkan di sisi lokal (sebelumnya akan terbaca 0, yang NDMI sah). tests/test_02f_ndmi.py memakai Earth Engine tiruan yang menolak urutan panggilan lama seperti Earth Engine asli

## v0.19
- scripts/02e_worldcover.py: kelas dominan dan pecahan tiap kelas ESA WorldCover v200 per sel 100 m pada grid induk (lulc.tif); 08 memakainya untuk penutup, 14 dan 15 sebagai fitur statis
- scripts/02f_grid_dynamic.py: hujan GSMaP (definisi sama dengan fitur stasiun) dan kelembapan tanah ERA5-Land (ECMWF/ERA5_LAND/DAILY_AGGR, volumetric_soil_water_layer_1) di PUSAT PIKSEL produk
  (transformasi dibaca dari Earth Engine), komposit NDMI per jendela (definisi sama dengan 02_gee_features.build_s2) sebagai raster per jendela; pembaruan inkremental
- scripts/02g_dynamic_features.py + src/dynfeat.py: fitur KAUSAL (jumlah hujan 1/7/14/30 hari, HTH, anomali terhadap tahun-tahun sebelumnya, kelembapan tanah, NDMI, ENSO/IOD bulan sebelumnya),
  dynamic.tif (keadaan terbaru, lebih besar = lebih kering) dan dynamic_reference.json (kuantil historis)
- src/cells.py: pemuat bersama kubus sel 1 km; fitur dinamis dalam empat format (sel-hari, piksel-hari, regional, sel-jendela tanpa melihat ke depan); 14_fire_model.py memakainya (--dynamic banyak berkas)
- 08_susceptibility.py: mode struktural+dinamis (hujan, HTH, kelembapan tanah, NDMI) dengan peringkat terhadap acuan HISTORIS dan batas kelas tetap (kuintil teoretis); menolak peringkat dinamis tanpa acuan historis
- scripts/15_dryness_cell_model.py: prakiraan pengeringan 7 dan 14 hari per sel (LightGBM kuantil dan klasifikasi turun >= 10 cm), fitur sel identik untuk stasiun dan peta, uji RUANG-WAKTU
  (stasiun ditahan dan tanggal sesudah titik potong), gerbang bukti; keluaran sel untuk web
- webmap prediksi: pilihan tema tunggal (peluang titik api, pengeringan per sel, kerentanan struktural), tiga lencana bukti, legenda mengikuti tema; 09 mengekspor dry_cells.geojson dan status masukan dari berkas yang ada

## v0.18
- src/grid.py: grid induk equal-area ESRI:54034 (paralel standar 0, hampir tanpa distorsi bentuk di ekuator: <= 0,55% pada 6 derajat; EPSG:6933 menjadikan sel 1 km
  1,15 x 0,87 km), sel berjangkar di (0,0) dan bersarang 100 m, 500 m, 1 km, id sel bilangan bulat. 07_grid_static.py memakainya (--crs utm = perilaku lama).
  Perlu dijalankan ulang: 07, 08, 10, 09 (keluaran lama berada di UTM dan tidak sejajar)
- scripts/12_fetch_firms.py: API area FIRMS (potongan 1-10 hari, MAP_KEY dari FIRMS_MAP_KEY, kunci tidak pernah ditulis), mode arsip tahunan; berkas L0 bertanggal, atomik,
  dilewati bila sudah ada; respons bukan CSV ditolak ke rejects.jsonl; manifest dengan sha256 dan jenis data SP/NRT
- scripts/13_hotspots_to_cells.py: titik api bersih (SNPP saja, type 0, tanpa duplikat, tanggal WIB, sumber persisten dibuang) dan tabel sel-hari 1 km, dengan catatan baris per tahap
- scripts/14_fire_model.py: LightGBM peluang titik api 1 dan 3 hari per sel 1 km; fitur hanya data <= t (diuji tiap run); pembagian waktu latih, kalibrasi isotonik, uji; pembanding
  klimatologi dan persistensi; gerbang (PR-AUC, skill Brier, Brier lawan persistensi); fitur dinamis opsional per sel-hari atau deret regional
- webmap: tiga halaman: index (beranda), monitoring (kondisi kini: kerentanan struktural, titik api teramati 7 hari, stasiun) dan prediction (peluang titik api, prakiraan stasiun);
  mesin peta bersama app.js (window.PAGE); panel faktor penyusun menampilkan status masukan apa adanya; style.css bersama
- 09_export_web.py: hotspots_recent.geojson, fire_cells.geojson, manifest.hotspots/fire/drivers; archive_run.py mengarsipkan fire_prob dan model

## v0.17.2
- webmap: dari file:// tidak ada lagi permintaan tile OSM (OSM menjawab 403 "Access blocked" untuk permintaan tanpa Referer); hanya petunjuk menjalankan http.server yang tampil.
  Tile OSM meminta referrerPolicy "origin" dan halaman memakai meta referrer origin-when-cross-origin supaya asal halaman terkirim sebagai Referer

## v0.17.1
- webmap: peta dasar OpenStreetMap standar (tanpa kunci API) dengan atribusi dan filter peredam warna; URL dapat diganti lewat `webmap.basemap` di config.yaml (masuk manifest)
- docs: keputusan peta dasar dan usulan arsitektur data (monitoring dan predicting) di CATATAN_DESAIN_DAN_REVISI.md

## v0.17
- 10_build_tiles.py: tile hillshade dari DEM 30 m (bayangan transparan, relief diperbesar 15x, kontras diregangkan otomatis, kompresi lunak); deskriptor memuat
  skema kelas, keterangan "tanpa warna = tidak dinilai", dan catatan hillshade
- 09_export_web.py: relief lokal dihapus; jarak ke stasiun dan AOA hanya dengan --advanced-layers
- webmap: grid tanpa goresan abu-abu; stasiun satu simbol (kelas muka air divergen di ambang -40 cm, abu-abu = tanpa data, putus-putus = berhenti melapor), prakiraan hanya di popup
  dengan peringatan jujur; hillshade di bawah kerawanan; legenda di peta; angka berformat Indonesia; kontrol opasitas diperjelas

## v0.16
- scripts/08_susceptibility.py: indeks kerawanan relatif per sel (struktural; dinamis bila dynamic.tif ada), peringkat terhadap distribusi acuan tetap
  (reference_quantiles.json) agar kelas stabil antar-run, penutup air/terbangun/bakau (WorldCover) dan gambut (BlueBook)
- scripts/10_build_tiles.py: tampilan tiga tingkat untuk hosting statis (unit KHG atau blok 5 km; tile 500 m; tile 100 m), kepercayaan sebagai
  transparansi dan arsiran, batas KHG/administrasi dan kanal sebagai garis; menulis webmap/data/kerawanan.json
- 09_export_web.py: peta panas kanal dihapus dari lapisan pendukung (terbaca sebagai hotspot), palet netral untuk jarak, kerawanan.json ditanam di manifest
- webmap: peta dasar abu muda, skala dan arah utara, penampil tiga tingkat per zoom, legenda kerawanan dan kepercayaan, kanal dan batas sebagai garis
- docs/CATATAN_DESAIN_DAN_REVISI.md: keputusan, daftar revisi diagram, jebakan, status, pertanyaan terbuka, dan cara menjalankan

## v0.15.1
- 06: median kini model kuantil 0,5 dan ketiga kuantil diurutkan per baris (q10 <= median <= q90), memperbaiki median yang melampaui q90
  (sebelumnya median dari regresi rata-rata dan kuantil terpisah); kolom `suspect` menandai prediksi yang jauh melampaui perubahan
  teramati di data latih; ringkasan walk-forward memuat `n_suspect`
- 04: kuantil dicegah bersilang sebelum menghitung cakupan q10-q90

## v0.15
- 01b: tiap run menulis ke data/raw/sitmat/details/<YYYYMMDD>/<id>_d90.json.gz dan tidak menimpa run lama; bawaan hanya stasiun aktif
  di potret (--all untuk semua); run ulang di hari yang sama dilanjutkan tanpa permintaan; berkas dikompres (--no-gzip untuk menolak)
- 01_stations: menggabungkan semua run per stasiun (berkas lama langsung di details/ tetap terbaca), membuang duplikat waktu dengan
  nilai run terbaru menang, sehingga deret terus memanjang melampaui jendela SiTMAT (sekitar 30 hari data 30 menitan, 90 hari harian)
- scripts/archive_run.py: arsip ringan per run (prediksi yang diterbitkan, metrik, run_meta.json, manifest) di outputs/arsip/ plus
  index.csv; dasar untuk penilaian prospektif

## v0.14.1
- webmap: peta dasar tampil sebelum data dimuat, dan pesan galat menjelaskan bahwa halaman tidak boleh dibuka lewat file:// (peramban
  memblokir fetch); jalankan `python -m http.server -d webmap 8000` lalu buka http://localhost:8000

## v0.14
- 07: kerapatan kanal sebagai peta panas (kernel Gaussian sigma 250 m dan 500 m; band `canal_kde_250m`, `canal_kde_500m`), menggantikan
  jendela melingkar; diuji terhadap nilai analitik
- scripts/09_export_web.py dan webmap/ (Leaflet): hamparan PNG, GeoJSON stasiun, deret waktu, dan manifest (versi, data sampai, status
  validasi, legenda, atribusi, penafian). Bagian JavaScript diuji dengan node (fungsi murni dan pengambilan lewat server statis);
  tampilan di peramban belum diperiksa
- docs/WEBGIS_DAN_OTOMASI.md: alur pembaruan otomatis, kebijakan latih ulang, dan daftar yang belum dibangun

## v0.13
- scripts/07_grid_static.py: grid area pilot (UTM, default 100 m), fitur statis per sel (FABDEM: elevasi, kemiringan, relief 500 m/1 km;
  kanal: kerapatan 500 m/1 km dari panjang kanal per sel), fitur yang sama di sel stasiun (konsistensi latih dan terap), dan komponen
  kepercayaan statis: jarak ke stasiun, jumlah stasiun 10 km, indeks ketidakmiripan dan area penerapan (AOA)
- src/confidence.py: skor kepercayaan 'rantai terlemah' (jarak, AOA, masukan, rentang prediksi), kelas rendah/sedang/tinggi, faktor
  pembatas, dan batas kelas dari bukti skill validasi

## v0.12
- scripts/06_predict.py: prediksi ke depan per stasiun (delta muka air h hari: median dan q10-q90; peluang turun >= d cm) pada
  tanggal terbit tertentu, dan `--walk-forward` (terbitkan tiap minggu hanya dengan data yang sudah diketahui, nilai setelah kenyataan
  tiba; dibanding persistensi dan frekuensi kejadian). Prototipe: peluang belum dikalibrasi
- src/modeling.py: konstanta dan pembantu model dipakai bersama 04 dan 06

## v0.11
- scripts/02d_canal_density.py: kerapatan kanal (km/km2, radius 500 m dan 1 km) di sekitar stasiun dari kanal_osm_clip.gpkg
  (hanya kerapatan, tanpa jenis kanal); proyeksi azimutal lokal per stasiun
- 03 menggabungkan canal_density.parquet; 04 memakai canal_density_500m dan canal_density_1km sebagai fitur statis

## v0.10
- FABDEM: scripts/02c_fabdem_pilot.py mengambil hanya ubin area pilot dari arsip data.bris lewat HTTP Range (`--check` untuk uji
  dukungan Range dan isi arsip), menghasilkan klip GeoTIFF dan fitur medan di stasiun (dem_fabdem.parquet)
- 02: grup `fabdem` (katalog komunitas Earth Engine) sebagai jalur alternatif
- 03 dan 04: fitur `fabdem_elev_m`, `fabdem_slope_deg`, `fabdem_relief_500m`, `fabdem_relief_1km`

## v0.9
- ENSO/IOD: src/enso.py (pembaca format standar PSL, ONI dan sstoi CPC), scripts/02b_enso.py (tabel bulanan; `--auto`
  mengunduh berkas CPC), 03 menggabungkan nino34/oni/dmi dengan lag 1 bulan, 04 punya `--with-enso` (bawaan mati)
- Modul musiman: 02 grup `chirps_long` (CHIRPS Jun-Nov sejak 1981) dan scripts/05_seasonal_outlook.py (leave-one-year-out,
  skill terhadap klimatologi; metrik musim: rain_total, hth_max, dry_frac)
- 03: fitur HTH BMKG (`dry_cat`, `dry_max_30d`, `rain_days_30d`) di samping `dry_days`
- 03: anomali komposit per stasiun (`vv_anom`, `vh_anom`, `ndmi_anom`, median berjalan); 04 memakai anomali (`--abs-sat` untuk menambah mutlak)
- 02: hujan GSMaP dijumlahkan pada hari lokal WIB (`--rain-tz-offset`), sejajar dengan hari muka air

## v0.8
- 02: perbaikan S2 (citra satu band: reduceRegions menamai hasil `mean`; kini diterima lewat `fallback_key`);
  peringatan bila satu kelompok menghasilkan 0 baris; hasil kosong tidak ditulis ke parquet
- 03: QC lonjakan harian (`--max-jump-p95`, default 30 cm; stasiun terburuk dicetak), diagnostik kebisingan nilai harian
  history vs median 30 menit, fitur tren muka air `wl_d3`/`wl_d7`, opsi `--smooth-days`, kolom ORACLE `fut_rain_7d/14d`
- 04: baseline AR (`ridge_ar`) berbasis muka air dan tren, varian `oracle_rain` (batas atas jika hujan masa depan diketahui),
  kejadian pengeringan (`turun>=d cm`, config `drop_events_cm`), opsi `--no-static`

## v0.7
- 02: Sentinel-1/2 dihitung per jendela dan per kelompok stasiun yang berdekatan (`--batch-size`, `--tile-scale`),
  `filterBounds` pada titik (bukan kotak batas seluruh stasiun), dan kelompok yang gagal karena memori dibelah dua lalu diulang
  (perbaikan "User memory limit exceeded" pada S2)
- 02: stasiun di luar Sumatra/Kalimantan/Papua dan sensor datar tidak diproses
- Tambah src/regions.py; 01_stations mencetak ringkasan wilayah; pick_pilot dan 03_assemble mengeluarkan stasiun di luar
  Sumatra/Kalimantan/Papua (`--keep-other-regions` untuk menahan); model_table memuat kolom `region`
- 04_baseline: skema LOIO (leave-one-island-out)

## v0.6
- 02: DEM beralih ke COPERNICUS/DEM/GLO30_2024_1 (yang lama usang); tambah grup `gsmap` (hujan near-real-time); default `--only static,gsmap`
- 03: pilih sumber hujan (`--rain-source auto|gsmap|chirps`) dan cetak kesesuaian gsmap vs chirps bila keduanya ada
- Alasan: CHIRPS di GEE berhenti 30 Sep 2026, padahal data muka air sampai 8 Nov
- 02: dengan --limit, keluaran bernama gee_<kelompok>_testN.parquet (tidak menimpa berkas penuh)

## v0.5
- 01_stations: tambah bendera flat_sensor (sensor datar di sekitar nol) dan wl_std_cm; alasan jelas untuk respons kosong
- pick_pilot dan 03_assemble mengeluarkan sensor datar (03: --keep-flat untuk menahannya)

## v0.4
- Tulis 02_gee_features (static, chirps, s1, s2; berkas yang ada dilewati), 03_assemble, 04_baseline
- Tambah src/gee_utils.py (pembantu murni-Python yang diuji)
- 04_baseline: skema LOSO, LOCO, TEMPORAL; baseline; LightGBM titik dan kuantil; metrik kejadian
- Catatan: bagian GEE di 02 belum diuji pada Earth Engine sungguhan

## v0.3
- Tambah: 01a_snapshot_sitmat, 01b_scrape_station_details, 01_stations (nyata), pick_pilot
- Tambah: src/sitmat_parse.py (parser station-detail), opsi `name` di src/polite_http.py
- Pindah: skrip pemeriksaan sekali pakai ke tools/
- README memuat tabel skrip dan statusnya

## v0.2
- environment.yml untuk seluruh alur, setup_env.sh, check_env.py

## v0.1
- Kerangka awal: config.yaml, 00_setup, test_polite_http, stub 01-04
