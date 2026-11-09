# Changelog

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
