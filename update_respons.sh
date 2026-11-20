#!/usr/bin/env bash
# update_respons.sh: tarik laporan Kobo terbaru -> buku besar -> response.json -> terbitkan ke GitHub Pages (lokal; bukan dari zip web).
#
#   ./update_respons.sh              # hanya mengolah dan menerbitkan bila ada laporan baru/berubah di Kobo
#   ./update_respons.sh --force      # olah dan terbitkan walau tidak ada yang baru
#   ./update_respons.sh --no-publish # olah saja, tidak menerbitkan
#
# Dirancang untuk dijalankan terjadwal (Task Scheduler Windows -> wsl.exe). Token TIDAK disimpan di repo:
#   ~/.config/peat-ew/kobo.env berisi baris  KOBO_TOKEN=...  (izin 600; skrip menolak bila bisa dibaca orang lain)
# Opsional di berkas yang sama: KOBO_ASSET=..., KOBO_SERVER=...
# Log: outputs/logs/respons_<waktu>.log. Hanya satu jalan sekaligus (kunci flock).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

FORCE=0; PUBLISH=1
for a in "$@"; do case "$a" in --force) FORCE=1 ;; --no-publish) PUBLISH=0 ;; *) echo "opsi tidak dikenal: $a"; exit 2 ;; esac; done

mkdir -p outputs/logs
exec 9>outputs/logs/.update_respons.lock
flock -n 9 || { echo "update_respons sedang berjalan; keluar."; exit 0; }
LOG="outputs/logs/respons_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1
echo "== update_respons $(date '+%F %T')"

SECRETS="$HOME/.config/peat-ew/kobo.env"
[[ -f "$SECRETS" ]] || { echo "GALAT: $SECRETS belum ada (isi: KOBO_TOKEN=...)."; exit 1; }
[[ "$(stat -c %a "$SECRETS")" == "600" ]] || { echo "GALAT: izin $SECRETS harus 600 (chmod 600 $SECRETS)."; exit 1; }
set -a; source "$SECRETS"; set +a
: "${KOBO_TOKEN:?KOBO_TOKEN kosong di $SECRETS}"
KOBO_ASSET="${KOBO_ASSET:-aYFk7zwjP9nVTWSJAftCth}"
KOBO_SERVER="${KOBO_SERVER:-https://kf.kobotoolbox.org}"

PY="${PY:-$HOME/miniconda3/envs/peat/bin/python}"
[[ -x "$PY" ]] || { echo "GALAT: python env peat tidak ada di $PY"; exit 1; }
export PROJ_DATA="${PROJ_DATA:-$("$PY" -c 'import pyproj; print(pyproj.datadir.get_data_dir())')}"

MAN=data/raw/laporan/manifest.jsonl
last_sha() { [[ -f "$MAN" ]] && grep '"source": "kobo"' "$MAN" | tail -1 | sed -E 's/.*"sha256": "([0-9a-f]+)".*/\1/' || true; }
BEFORE="$(last_sha)"

echo "-- 16 tarik Kobo ($KOBO_SERVER aset $KOBO_ASSET)"
"$PY" scripts/16_ingest_reports.py --kobo-asset "$KOBO_ASSET" --kobo-server "$KOBO_SERVER"
unset KOBO_TOKEN
AFTER="$(last_sha)"

if [[ $FORCE -eq 0 && -n "$BEFORE" && "$BEFORE" == "$AFTER" ]]; then
  echo "Tidak ada laporan baru atau berubah di Kobo (olah ulang dilewati)."
else
  echo "-- 17 buku besar kejadian"
  "$PY" scripts/17_event_ledger.py
  echo "-- 20 ekspor response.json"
  "$PY" scripts/20_export_response.py
fi

# terbitkan bila response.json berbeda dari yang terakhir diterbitkan (mis. jalan sebelumnya --no-publish)
STAMP=outputs/logs/.respons_published.sha256
CUR="$(sha256sum webmap/data/response.json | cut -d' ' -f1)"
if [[ $PUBLISH -eq 0 ]]; then
  echo "(--no-publish: tidak diterbitkan)"
elif [[ $FORCE -eq 0 && -f "$STAMP" && "$(cat "$STAMP")" == "$CUR" ]]; then
  echo "response.json sama dengan yang sudah terbit; tidak menerbitkan."
else
  echo "-- terbitkan ke GitHub Pages"
  ./publish_pages.sh --yes
  echo "$CUR" > "$STAMP"
fi
echo "== selesai $(date '+%F %T') | log: $LOG"
