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
| scripts/01b_scrape_station_details.py | ambil station-detail semua stasiun | siap |
| scripts/01_stations.py | bersihkan dan gabungkan jadi parquet | siap |
| scripts/pick_pilot.py | pilih klaster stasiun untuk pilot | siap |
| scripts/02_gee_features.py | fitur Earth Engine di titik stasiun (static, gsmap, chirps, s1, s2) | siap; bagian GEE belum diuji pada GEE sungguhan |
| scripts/03_assemble.py | gabung target harian dan fitur jadi model_table | siap (diuji data sintetik) |
| scripts/04_baseline.py | baseline, LightGBM, kuantil, validasi LOSO/LOCO/TEMPORAL | siap (diuji data sintetik) |

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
