#!/usr/bin/env bash
# run_pipeline.sh: jalankan alur peringatan dini gambut dari awal sampai webmap.
#
# Pemakaian:
#   ./run_pipeline.sh                              # semua tahap lokal (fitur, model, peta); tahap internet dilewati
#   ./run_pipeline.sh --contact email@kamu.ac.id   # ikut ambil data SiTMAT baru dan FABDEM (butuh email kontak)
#   ./run_pipeline.sh model peta                   # hanya tahap tertentu
#   ./run_pipeline.sh --refresh-gee fitur          # ambil ulang fitur Earth Engine (wajib setelah data SiTMAT baru)
#   ./run_pipeline.sh --serve                      # di akhir, buka server webmap di http://localhost:8000
#   ./run_pipeline.sh --arsip --label "minggu 1"   # di akhir, arsipkan prediksi + metrik ke outputs/arsip/<waktu>/
#   ./run_pipeline.sh --arsip-web                  # sama, tetapi seluruh webmap/data ikut diarsipkan
#
# Tahap (urutan tetap): stasiun -> fitur -> model -> peta [-> arsip]
#   stasiun : 01a potret SiTMAT, 01b detail stasiun (aktif saja; folder bertanggal, tidak menimpa run lama),
#             01 tabel bersih (menggabungkan semua run), pick_pilot   (internet; butuh --contact)
#   fitur   : 02 Earth Engine, 02b ENSO, 02c FABDEM (internet; butuh --contact), 02d kerapatan kanal
#   model   : 03 tabel model, 04 baseline --quick, 06 prediksi, 06 --walk-forward
#   peta    : 07 grid statis (butuh FABDEM), 09 ekspor webmap
#
# Log tiap jalan disimpan di outputs/logs/run_<tanggal>.log. Skrip berhenti pada galat pertama di tahap wajib;
# tahap opsional yang syaratnya belum ada dilewati dengan pesan.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# ---------- pilihan ----------
CONTACT=""
REFRESH_GEE=0
SERVE=0
PORT=8000
ARSIP=0
ARSIP_WEB=0
LABEL=""
STAGES=()
PILOT_BBOX=(103.68 -1.61 104.17 -1.12)   # klaster 5 (pesisir Jambi)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --contact) CONTACT="${2:-}"; shift 2 ;;
    --refresh-gee) REFRESH_GEE=1; shift ;;
    --serve) SERVE=1; shift ;;
    --port) PORT="${2:-8000}"; shift 2 ;;
    --arsip) ARSIP=1; shift ;;
    --arsip-web) ARSIP=1; ARSIP_WEB=1; shift ;;
    --label) LABEL="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
    stasiun|fitur|model|peta) STAGES+=("$1"); shift ;;
    *) echo "Pilihan tidak dikenal: $1 (lihat ./run_pipeline.sh --help)"; exit 2 ;;
  esac
done
[[ ${#STAGES[@]} -eq 0 ]] && STAGES=(stasiun fitur model peta)
want() { [[ " ${STAGES[*]} " == *" $1 "* ]]; }

# ---------- Python env peat ----------
PY="${PY:-}"
if [[ -z "$PY" ]]; then
  for cand in "${CONDA_PREFIX:-}/bin/python" "$HOME/miniconda3/envs/peat/bin/python" "$HOME/anaconda3/envs/peat/bin/python" "$(command -v python || true)"; do
    if [[ -x "$cand" ]] && "$cand" -c "import ee, lightgbm, geopandas, rasterio" 2>/dev/null; then PY="$cand"; break; fi
  done
fi
if [[ -z "$PY" ]]; then
  echo "Python env 'peat' tidak ditemukan. Aktifkan dulu: conda activate peat"; exit 1
fi
# GDAL kadang tidak menemukan basis data PROJ; arahkan ke milik pyproj
export PROJ_DATA="${PROJ_DATA:-$("$PY" -c 'import pyproj; print(pyproj.datadir.get_data_dir())')}"

# ---------- log ----------
mkdir -p outputs/logs
LOG="outputs/logs/run_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1
echo "== run_pipeline $(date '+%Y-%m-%d %H:%M:%S') | python: $PY | tahap: ${STAGES[*]}"
echo "== log: $LOG"

declare -a SUMMARY=()
T_START=$(date +%s)

run() {  # run "nama" perintah... ; berhenti bila gagal
  local name="$1"; shift
  local t0=$(date +%s)
  echo; echo "---------- [$name] $*"
  "$@" 2> >(grep -v -E "UserWarning|warnings.warn" >&2)
  local rc=$?
  local dt=$(( $(date +%s) - t0 ))
  if [[ $rc -ne 0 ]]; then
    SUMMARY+=("GAGAL   $name (${dt}s)")
    echo; echo "!! [$name] gagal (kode $rc). Lihat $LOG"; print_summary; exit $rc
  fi
  SUMMARY+=("OK      $name (${dt}s)")
}
skip() { echo; echo "---------- [$1] DILEWATI: $2"; SUMMARY+=("lewat   $1: $2"); }
print_summary() {
  echo; echo "========== Ringkasan ($(( $(date +%s) - T_START ))s)"
  printf '  %s\n' "${SUMMARY[@]}"
  echo "  log: $LOG"
}

# ---------- tahap: stasiun ----------
if want stasiun; then
  if [[ -z "$CONTACT" ]]; then
    skip "01a/01b SiTMAT" "butuh --contact EMAIL (memakai data SiTMAT yang sudah ada)"
  else
    run "01a potret SiTMAT" "$PY" scripts/01a_snapshot_sitmat.py --contact "$CONTACT"
    run "01b detail stasiun" "$PY" scripts/01b_scrape_station_details.py --contact "$CONTACT"
    [[ $REFRESH_GEE -eq 0 ]] && echo "   Catatan: data SiTMAT baru -> pakai --refresh-gee agar fitur Earth Engine ikut diperbarui."
  fi
  run "01 tabel stasiun" "$PY" scripts/01_stations.py
  run "pick_pilot" "$PY" scripts/pick_pilot.py
fi

# ---------- tahap: fitur ----------
if want fitur; then
  GEE_ARGS=(--only static,gsmap,chirps,s1,s2)
  [[ $REFRESH_GEE -eq 1 ]] && GEE_ARGS+=(--force)
  run "02 Earth Engine" "$PY" scripts/02_gee_features.py "${GEE_ARGS[@]}"

  if compgen -G "data/raw/enso/*" > /dev/null; then
    run "02b ENSO" "$PY" scripts/02b_enso.py
  else
    skip "02b ENSO" "belum ada berkas di data/raw/enso/"
  fi

  if [[ -f data/raw/dem/fabdem_pilot.tif ]]; then
    skip "02c FABDEM" "fabdem_pilot.tif sudah ada"
  elif [[ -n "$CONTACT" ]]; then
    run "02c FABDEM" "$PY" scripts/02c_fabdem_pilot.py --bbox "${PILOT_BBOX[@]}" --contact "$CONTACT"
  else
    skip "02c FABDEM" "butuh --contact EMAIL untuk mengunduh"
  fi

  if [[ -f data/raw/kanal/kanal_osm_clip.gpkg ]]; then
    run "02d kerapatan kanal" "$PY" scripts/02d_canal_density.py
  else
    skip "02d kerapatan kanal" "data/raw/kanal/kanal_osm_clip.gpkg tidak ada"
  fi
fi

# ---------- tahap: model ----------
if want model; then
  run "03 tabel model" "$PY" scripts/03_assemble.py
  run "04 baseline" "$PY" scripts/04_baseline.py --quick
  run "06 prediksi" "$PY" scripts/06_predict.py
  run "06 walk-forward" "$PY" scripts/06_predict.py --walk-forward
fi

# ---------- tahap: peta ----------
if want peta; then
  if [[ -f data/raw/dem/fabdem_pilot.tif ]]; then
    run "07 grid statis" "$PY" scripts/07_grid_static.py
  else
    skip "07 grid statis" "butuh data/raw/dem/fabdem_pilot.tif (jalankan dengan --contact untuk 02c)"
  fi
  run "09 ekspor webmap" "$PY" scripts/09_export_web.py
fi

# ---------- arsip (opsional) ----------
if [[ $ARSIP -eq 1 ]]; then
  ARSIP_ARGS=()
  [[ -n "$LABEL" ]] && ARSIP_ARGS+=(--label "$LABEL")
  [[ $ARSIP_WEB -eq 1 ]] && ARSIP_ARGS+=(--include-web)
  run "arsip run" "$PY" scripts/archive_run.py "${ARSIP_ARGS[@]}"
fi

print_summary

if [[ $SERVE -eq 1 ]]; then
  echo; echo "Webmap: http://localhost:$PORT  (Ctrl+C untuk berhenti)"
  "$PY" -m http.server -d webmap "$PORT"
fi
