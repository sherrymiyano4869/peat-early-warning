# Peat early warning (AGC 2027)

## Pasang lingkungan (sekali)
    bash setup_env.sh
    conda activate peat
    earthengine authenticate --quiet
    # isi gee.project di config.yaml

## Skrip utama (jalankan berurutan dari folder proyek)
| Skrip | Fungsi | Status |
|---|---|---|
| scripts/check_env.py | cek semua pustaka terpasang | siap |
| scripts/00_setup.py | uji koneksi Earth Engine | siap |
| scripts/01a_snapshot_sitmat.py | potret daftar stasiun SiTMAT (jalankan tiap 1-2 minggu) | siap |
| scripts/01b_scrape_station_details.py | ambil station-detail ke folder bertanggal per run (tidak menimpa) | siap |
| scripts/01_stations.py | bersihkan dan gabungkan jadi parquet | siap |
| scripts/pick_pilot.py | pilih klaster stasiun untuk pilot | siap |
| scripts/02_gee_features.py | fitur Earth Engine di titik stasiun (static, gsmap, chirps, s1, s2) | siap; static, gsmap, chirps, s1 teruji di GEE; s2 versi v0.7 belum diuji |
| scripts/02d_canal_density.py | kerapatan kanal di sekitar stasiun dari gpkg kanal OSM (atribusi OSM wajib) | siap (diuji hitungan analitik) |
| scripts/02c_fabdem_pilot.py | FABDEM area pilot dari data.bris (Range) dan fitur medan di stasiun | siap (diuji server tiruan; server asli belum) |
| scripts/02b_enso.py | tabel ENSO/IOD bulanan dari berkas NOAA (data/raw/enso/) | siap (diuji data sintetik; format berkas dari ingatan) |
| scripts/03_assemble.py | gabung target harian dan fitur jadi model_table | siap (diuji data sintetik) |
| scripts/04_baseline.py | baseline, LightGBM, kuantil, validasi LOSO/LOCO/LOIO/TEMPORAL | siap (diuji data sintetik) |
| scripts/archive_run.py | arsip ringan per run (prediksi terbit, metrik, run_meta) di outputs/arsip/ | siap (diuji data tiruan) |
| scripts/02e_worldcover.py | tutupan lahan WorldCover (kelas dominan dan pecahan) pada grid induk 100 m | siap (bagian lokal diuji; Earth Engine belum dicoba) |
| scripts/02f_grid_dynamic.py | hujan GSMaP, kelembapan tanah ERA5-Land (per piksel produk), dan komposit NDMI Sentinel-2 per sel, inkremental | siap (bagian lokal diuji; Earth Engine belum dicoba) |
| scripts/02g_dynamic_features.py | fitur kausal (hujan, HTH, anomali, tanah, NDMI, ENSO), dynamic.tif dan acuan historis | siap (diuji data tiruan) |
| scripts/15_dryness_cell_model.py | prakiraan pengeringan 7 dan 14 hari per sel (kuantil + peluang), uji ruang-waktu, gerbang bukti | siap (diuji data tiruan) |
| scripts/12_fetch_firms.py | titik api VIIRS dari FIRMS (API area dengan MAP_KEY, atau arsip tahunan tanpa kunci) ke L0 bertanggal | siap (diuji server tiruan; server FIRMS belum dicoba) |
| scripts/13_hotspots_to_cells.py | titik api bersih (L1) dan tabel sel-hari 1 km, dengan catatan baris tiap tahap | siap (diuji data tiruan) |
| scripts/14_fire_model.py | LightGBM peluang titik api 1 dan 3 hari per sel 1 km, pembanding, gerbang bukti | siap (diuji data tiruan; belum di data nyata) |
| scripts/08_susceptibility.py | indeks kerawanan relatif per sel (struktural; dinamis bila ada) | siap (diuji data tiruan) |
| scripts/10_build_tiles.py | tile kerawanan tiga tingkat, unit KHG, batas, kanal untuk webmap | siap (diuji data tiruan) |
| scripts/09_export_web.py | ekspor hamparan, GeoJSON, deret waktu, manifest ke webmap/data (WebGIS Leaflet) | siap (diuji data tiruan) |
| scripts/07_grid_static.py | grid pilot, fitur statis per sel, dan kepercayaan statis (jarak stasiun, AOA) | siap (diuji data tiruan) |
| scripts/06_predict.py | prediksi ke depan per stasiun dan uji walk-forward mingguan | siap (diuji data sintetik); prototipe, belum terkalibrasi |
| scripts/05_seasonal_outlook.py | ENSO/IOD vs kekeringan musim (HTH, hujan) multi-tahun, leave-one-year-out | siap (diuji data sintetik) |

Contoh pemakaian:
    python scripts/01a_snapshot_sitmat.py --contact emailmu@contoh.com
    python scripts/01b_scrape_station_details.py --contact emailmu@contoh.com --limit 3
    python scripts/01_stations.py
    python scripts/pick_pilot.py
    python scripts/02_gee_features.py --dry-run
    python scripts/02_gee_features.py --limit 3 --only static,gsmap   # uji kecil
    python scripts/02_gee_features.py
    python scripts/03_assemble.py
    python scripts/04_baseline.py --quick

## Alat bantu (opsional, boleh diabaikan)
Folder `tools/` berisi skrip pemeriksaan sekali pakai: inspect_json, describe_station,
describe_stations, check_history, summarize_network. Pipeline tidak bergantung padanya.

## Catatan
- Taruh proyek di filesystem WSL (~/...), bukan di /mnt/c.
- Berkas `*:Zone.Identifier` hanyalah sisa unduhan Windows; aman dihapus:
    find . -name "*:Zone.Identifier" -delete
- Pembaruan dikirim sebagai satu zip lengkap; lihat CHANGELOG.md.


## Menjalankan titik api, grid induk, dan dua halaman web (v0.18)
    export FIRMS_MAP_KEY=...            # kunci gratis dari firms.modaps.eosdis.nasa.gov/api/map_key (BUKAN kata sandi Earthdata)
    python scripts/12_fetch_firms.py --source VIIRS_SNPP_SP  --start 2015-01-01 --end 2024-12-31   # riwayat sains untuk melatih
    python scripts/12_fetch_firms.py --source VIIRS_SNPP_NRT --start TGL --end TGL                 # hari-hari terakhir
    python scripts/07_grid_static.py                  # sekarang di grid induk equal-area (ESRI:54034); jalankan ulang 07, 08, 10, 09
    python scripts/08_susceptibility.py --peat-gpkg data/raw/batas/gambut.gpkg --peat-layer NAMA
    python scripts/13_hotspots_to_cells.py --peat-gpkg data/raw/batas/gambut.gpkg --peat-layer NAMA
    python scripts/14_fire_model.py                   # opsional: --dynamic data/features/dynamic_daily.parquet
    python scripts/10_build_tiles.py ...              # lihat docs/CATATAN_DESAIN_DAN_REVISI.md
    python scripts/09_export_web.py
    python -m http.server -d webmap 8000              # buka http://localhost:8000 (halaman: index, monitoring, prediction)
Lalu `python scripts/archive_run.py --label "..."` mengarsipkan juga peluang titik api (fire_prob_<tanggal>.parquet) untuk penilaian prospektif.


## Fitur dinamis per sel (v0.19)
    python scripts/02e_worldcover.py                          # setelah 07; sekali saja
    python scripts/02f_grid_dynamic.py --dry-run              # lihat rencana dan jumlah permintaan SEBELUM menyentuh Earth Engine
    python scripts/02f_grid_dynamic.py --only gsmap,era5soil --start 2015-01-01
    python scripts/02f_grid_dynamic.py --only ndmi --start 2018-12-01 --ndmi-step 30     # paling berat; satu bulan dulu
    python scripts/02b_enso.py                                # indeks ENSO/IOD bulanan (sudah ada)
    python scripts/02g_dynamic_features.py                    # fitur kausal + dynamic.tif + acuan historis
    python scripts/08_susceptibility.py --peat-gpkg ...       # kini otomatis struktural+dinamis bila dynamic.tif dan dynamic_reference.json ada
    python scripts/14_fire_model.py --dynamic data/features/dyn_rain_pixels.parquet data/features/dyn_soil_pixels.parquet data/features/dyn_ndmi_cells.parquet data/features/dyn_enso_daily.parquet
    python scripts/15_dryness_cell_model.py                   # perlu model_table.parquet (03) dan fitur dinamis
Pembaruan harian: 02f hanya meminta tanggal sesudah data terakhir (dikurangi --overlap-days); lalu 02g, 08, 14, 15, 10, 09.
