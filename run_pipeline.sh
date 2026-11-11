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
#   ./run_pipeline.sh dinamis titikapi            # peta + pembaruan fitur dinamis per sel dan titik api (opsional, v0.18-0.19)
#
# Tahap (urutan tetap): stasiun -> fitur -> model -> peta [-> arsip]
#   stasiun : 01a potret SiTMAT, 01b detail stasiun (aktif saja; folder bertanggal, tidak menimpa run lama),
#             01 tabel bersih (menggabungkan semua run), pick_pilot   (internet; butuh --contact)
#   fitur   : 02 Earth Engine, 02b ENSO, 02c FABDEM (internet; butuh --contact), 02d kerapatan kanal
#   model   : 03 tabel model, 04 baseline --quick, 06 prediksi, 06 --walk-forward
#   peta    : 07 grid statis (butuh FABDEM), 08 indeks kerawanan, 10 tile tiga tingkat, 09 ekspor webmap,
#             09b deret waktu area pilot untuk halaman Monitoring (skrip lokal)
#             Opsional (dipakai otomatis bila berkasnya ada; layer pertama dipakai bila --*-layer tidak diisi):
#               data/raw/batas/gambut.gpkg -> 08 --peat-gpkg   (atur dengan --peat-layer NAMA)
#               data/raw/batas/khg.gpkg    -> 10 --units-gpkg  (atur dengan --khg-layer NAMA --khg-name KOLOM)
#               data/raw/batas/admin.gpkg  -> 10 --admin-gpkg  (atur dengan --admin-layer NAMA)
#             Tanpa khg.gpkg, tingkat 1 memakai blok 5 km sementara.
#   dinamis : (opsional, menyertakan peta) 02e WorldCover (sekali, bila lulc.tif belum ada), 02f data dinamis per sel
#             INKREMENTAL (hanya kelompok yang berkasnya sudah ada di data/features/grid_dynamic/; unduhan awal 2015-an
#             dijalankan manual, lihat README), 02g fitur kausal + dynamic.tif, lalu 08 dihitung ulang (struktural+dinamis)
#   titikapi: (opsional, menyertakan peta) 12 FIRMS NRT 9 hari terakhir (butuh env FIRMS_MAP_KEY), 13 titik api ke sel,
#             14 model peluang titik api (butuh berkas di data/raw/firms/)
#   15 prakiraan pengeringan per sel dijalankan otomatis di peta bila fitur dinamis (dyn_rain/soil/ndmi) sudah ada.
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
PEAT_LAYER=""
KHG_LAYER=""
KHG_NAME=""
ADMIN_LAYER=""
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
    --peat-layer) PEAT_LAYER="${2:-}"; shift 2 ;;
    --khg-layer) KHG_LAYER="${2:-}"; shift 2 ;;
    --khg-name) KHG_NAME="${2:-}"; shift 2 ;;
    --admin-layer) ADMIN_LAYER="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,34p' "$0"; exit 0 ;;
    stasiun|fitur|model|peta|dinamis|titikapi) STAGES+=("$1"); shift ;;
    *) echo "Pilihan tidak dikenal: $1 (lihat ./run_pipeline.sh --help)"; exit 2 ;;
  esac
done
[[ ${#STAGES[@]} -eq 0 ]] && STAGES=(stasiun fitur model peta)
want() { [[ " ${STAGES[*]} " == *" $1 "* ]]; }
# dinamis dan titikapi berjalan di dalam tahap peta (butuh grid 07 dan kelas 08)
if { want dinamis || want titikapi; } && ! want peta; then STAGES+=(peta); fi

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
first_layer() { "$PY" -c 'import sys, pyogrio; print(pyogrio.list_layers(sys.argv[1])[0][0])' "$1" 2>/dev/null; }

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

  if [[ -f data/features/grid/static.tif ]]; then
    S08=()
    if [[ -f data/raw/batas/gambut.gpkg ]]; then
      S08+=(--peat-gpkg data/raw/batas/gambut.gpkg --peat-layer "${PEAT_LAYER:-$(first_layer data/raw/batas/gambut.gpkg)}")
    else
      echo "   (08: data/raw/batas/gambut.gpkg belum ada; sel di luar gambut belum dikeluarkan)"
    fi

    if want dinamis; then
      if [[ -f data/features/grid/lulc.tif ]]; then
        skip "02e WorldCover" "lulc.tif sudah ada (pakai 02e --force untuk ulang)"
      else
        run "02e WorldCover" "$PY" scripts/02e_worldcover.py
      fi
    fi
    run "08 indeks kerawanan" "$PY" scripts/08_susceptibility.py "${S08[@]}"

    if want dinamis; then
      GD=data/features/grid_dynamic; ONLY=()
      [[ -f $GD/rain_pixels.parquet ]] && ONLY+=(gsmap)
      [[ -f $GD/soil_pixels.parquet ]] && ONLY+=(era5soil)
      [[ -f $GD/ndmi_cells.parquet ]] && ONLY+=(ndmi)
      if [[ ${#ONLY[@]} -gt 0 ]]; then
        run "02f data dinamis (inkremental)" "$PY" scripts/02f_grid_dynamic.py --only "$(IFS=,; echo "${ONLY[*]}")"
      else
        skip "02f data dinamis" "belum ada unduhan awal di $GD/ (jalankan manual dulu, lihat README v0.19)"
      fi
      if compgen -G "$GD/*.parquet" > /dev/null; then
        run "02g fitur dinamis" "$PY" scripts/02g_dynamic_features.py
        run "08 indeks kerawanan (+dinamis)" "$PY" scripts/08_susceptibility.py "${S08[@]}"
      else
        skip "02g fitur dinamis" "belum ada data 02f"
      fi
    fi

    DYN=()
    for f in dyn_rain_pixels dyn_soil_pixels dyn_ndmi_cells dyn_enso_daily; do
      [[ -f data/features/$f.parquet ]] && DYN+=(data/features/$f.parquet)
    done

    if want titikapi; then
      if [[ -n "${FIRMS_MAP_KEY:-}" ]]; then
        F12=(--source VIIRS_SNPP_NRT)
        [[ -n "$CONTACT" ]] && F12+=(--contact "$CONTACT")
        run "12 FIRMS NRT" "$PY" scripts/12_fetch_firms.py "${F12[@]}"
      else
        skip "12 FIRMS" "env FIRMS_MAP_KEY belum diisi (memakai titik api yang sudah ada)"
      fi
      if [[ -d data/raw/firms ]] && [[ -n "$(find data/raw/firms -type f -name '*.csv*' 2>/dev/null | head -1)" ]]; then
        S13=()
        [[ -f data/raw/batas/gambut.gpkg ]] && S13+=(--peat-gpkg data/raw/batas/gambut.gpkg --peat-layer "${PEAT_LAYER:-$(first_layer data/raw/batas/gambut.gpkg)}")
        run "13 titik api ke sel" "$PY" scripts/13_hotspots_to_cells.py "${S13[@]}"
        S14=(); [[ ${#DYN[@]} -gt 0 ]] && S14+=(--dynamic "${DYN[@]}")
        run "14 model titik api" "$PY" scripts/14_fire_model.py "${S14[@]}"
      else
        skip "13 + 14 titik api" "belum ada berkas di data/raw/firms/"
      fi
    fi

    if [[ -f data/features/dyn_rain_pixels.parquet || -f data/features/dyn_soil_pixels.parquet || -f data/features/dyn_ndmi_cells.parquet ]]; then
      run "15 pengeringan per sel" "$PY" scripts/15_dryness_cell_model.py
    else
      skip "15 pengeringan per sel" "belum ada fitur dinamis (tahap dinamis / 02g)"
    fi

    S10=()
    if [[ -f data/raw/batas/khg.gpkg ]]; then
      S10+=(--units-gpkg data/raw/batas/khg.gpkg --units-layer "${KHG_LAYER:-$(first_layer data/raw/batas/khg.gpkg)}")
      [[ -n "$KHG_NAME" ]] && S10+=(--units-name "$KHG_NAME")
    else
      echo "   (10: data/raw/batas/khg.gpkg belum ada; tingkat 1 memakai blok 5 km sementara)"
    fi
    if [[ -f data/raw/batas/admin.gpkg ]]; then
      S10+=(--admin-gpkg data/raw/batas/admin.gpkg --admin-layer "${ADMIN_LAYER:-$(first_layer data/raw/batas/admin.gpkg)}")
    fi
    if [[ -f data/raw/kanal/kanal_osm_clip.gpkg ]]; then
      S10+=(--canal-gpkg data/raw/kanal/kanal_osm_clip.gpkg --canal-layer kanal_pilot_klaster5)
    fi
    run "10 tile tiga tingkat" "$PY" scripts/10_build_tiles.py "${S10[@]}"
  else
    skip "08 + 10" "butuh data/features/grid/static.tif dari 07"
  fi

  run "09 ekspor webmap" "$PY" scripts/09_export_web.py
  if [[ -f scripts/09b_export_timeseries.py ]]; then
    run "09b deret waktu monitoring" "$PY" scripts/09b_export_timeseries.py
  fi
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
