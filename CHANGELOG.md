# Changelog

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
