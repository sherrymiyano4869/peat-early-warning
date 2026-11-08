# Changelog

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
