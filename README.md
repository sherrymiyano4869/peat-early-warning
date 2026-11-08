# Peat early warning (AGC 2027)

Alur skrip (jalankan berurutan):
00_setup -> 01_stations -> 02_gee_features -> 03_assemble -> 04_baseline
Rencana berikutnya: 05 prakiraan 7-14 hari, 06 outlook musiman, 07 fusi dan kalibrasi, 08 dashboard.

## Pasang lingkungan di WSL (sekali saja)
    bash setup_env.sh
Skrip itu memasang conda (Miniforge) bila belum ada, membuat env `peat` dari
`environment.yml`, mendaftarkan kernel Jupyter "Python (peat)", dan menjalankan
`scripts/check_env.py`.

Lalu:
    conda activate peat
    earthengine authenticate --quiet
    # isi gee.project di config.yaml
    python scripts/00_setup.py
    python scripts/test_polite_http.py

Taruh proyek di filesystem WSL (misalnya ~/peat-early-warning), bukan di /mnt/c.

## Catatan
- Playwright (untuk situs yang wajib dirender browser) sengaja tidak dimasukkan.
  Pasang hanya jika memang dibutuhkan: `pip install playwright && playwright install chromium`.
- Earth Engine hanya dipakai untuk mengambil data. Pemodelan dilakukan lokal.
