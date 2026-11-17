#!/usr/bin/env bash
# update_data.sh: pembaruan data penuh dari sumber luar sampai webmap (lokal; bukan dari zip web).
#
#   conda activate peat
#   export FIRMS_MAP_KEY=...        # kunci FIRMS
#   export KOBO_TOKEN=...           # token API Kobo (akun sendiri)
#   export KONTAK=emailmu@contoh.com   # hanya untuk tahap SiTMAT; tanpa ini tahap SiTMAT dilewati
#   ./update_data.sh [--tanpa-ndmi] [--tanpa-stasiun] [--label "teks arsip"]
#
# Urutan (berhenti di galat pertama; log di outputs/logs/update_<waktu>.log):
#   1 SiTMAT + fitur stasiun + model muka air   run_pipeline.sh --contact --refresh-gee stasiun fitur model   (butuh KONTAK)
#   2 hujan GSMaP dan kelembapan tanah ERA5     02f inkremental
#   3 NDMI Sentinel-2 (paling lama)             02f --tile-deg 0.35 (tanpa itu Earth Engine menolak: batas memori)
#   4 titik api: celah arsip SP lalu NRT        12 (potongan yang sudah ada dilewati)
#   5 fitur dinamis kausal                      02g
#   6 peta: grid, kerawanan, titik api, model, tile, ekspor web, arsip      run_pipeline.sh peta titikapi --arsip
#   7 Kobo dan Respons                          16, 17, 18, 19, 20
set -uo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

NDMI=1; STASIUN=1; LABEL="update $(date +%F)"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tanpa-ndmi) NDMI=0; shift ;;
    --tanpa-stasiun) STASIUN=0; shift ;;
    --label) LABEL="${2:-$LABEL}"; shift 2 ;;
    -h|--help) sed -n '2,19p' "$0"; exit 0 ;;
    *) echo "Pilihan tidak dikenal: $1"; exit 2 ;;
  esac
done

PY="${PYTHON:-python}"
: "${FIRMS_MAP_KEY:?FIRMS_MAP_KEY belum diisi (export FIRMS_MAP_KEY=...)}"
: "${KOBO_TOKEN:?KOBO_TOKEN belum diisi (export KOBO_TOKEN=...)}"
export PROJ_DATA="${PROJ_DATA:-$("$PY" -c 'import pyproj;print(pyproj.datadir.get_data_dir())')}"
KOBO_ASSET="${KOBO_ASSET:-aYFk7zwjP9nVTWSJAftCth}"
TODAY="$(date +%F)"
mkdir -p outputs/logs
LOG="outputs/logs/update_$(date +%Y%m%d_%H%M%S).log"

run() {
  local name="$1"; shift
  echo; echo "=== $name  [$(date +%T)]" | tee -a "$LOG"
  "$@" 2>&1 | tee -a "$LOG"
  local rc=${PIPESTATUS[0]}
  if [[ $rc -ne 0 ]]; then echo "!!! GAGAL ($rc): $name. Lihat $LOG" | tee -a "$LOG"; exit "$rc"; fi
}

if [[ $STASIUN -eq 1 ]]; then
  if [[ -n "${KONTAK:-}" ]]; then
    run "1 SiTMAT + fitur stasiun + model" ./run_pipeline.sh --contact "$KONTAK" --refresh-gee stasiun fitur model
  else
    echo "(1 dilewati: KONTAK belum diisi; memakai data stasiun yang sudah ada)" | tee -a "$LOG"
  fi
fi

run "2 hujan dan kelembapan tanah" "$PY" scripts/02f_grid_dynamic.py --only gsmap,era5soil
if [[ $NDMI -eq 1 ]]; then
  run "3 NDMI" "$PY" scripts/02f_grid_dynamic.py --only ndmi --ndmi-step 30 --tile-deg 0.35
else
  echo "(3 NDMI dilewati: --tanpa-ndmi)" | tee -a "$LOG"
fi

run "4a FIRMS SP (arsip, celah 2025 sampai Juli 2026)" "$PY" scripts/12_fetch_firms.py --source VIIRS_SNPP_SP --start 2025-01-01 --end 2026-07-31
run "4b FIRMS NRT (Agustus 2026 sampai hari ini)" "$PY" scripts/12_fetch_firms.py --source VIIRS_SNPP_NRT --start 2026-08-01 --end "$TODAY"

run "5 fitur dinamis kausal" "$PY" scripts/02g_dynamic_features.py

run "6 peta, titik api, model, tile, web, arsip" ./run_pipeline.sh peta titikapi --arsip --label "$LABEL"

run "7a Kobo: tarik laporan" "$PY" scripts/16_ingest_reports.py --kobo-asset "$KOBO_ASSET"
run "7b buku besar kejadian" "$PY" scripts/17_event_ledger.py
run "7c skor prospektif" "$PY" scripts/18_score_prospective.py
run "7d tugas pemeriksaan (dari prediksi terbaru)" "$PY" scripts/19_verification_tasks.py
run "7e ekspor halaman Respons" "$PY" scripts/20_export_response.py

echo; echo "SELESAI. Buka webnya:  python -m http.server -d webmap 8000   lalu http://localhost:8000" | tee -a "$LOG"
