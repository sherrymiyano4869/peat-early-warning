#!/usr/bin/env bash
# publish_pages.sh: terbitkan webmap/ ke GitHub Pages lewat cabang gh-pages (lokal; bukan dari zip web).
#
#   ./publish_pages.sh --dry-run     # hanya membangun salinan dan melaporkan ukuran; TIDAK mengirim apa pun
#   ./publish_pages.sh               # tanya konfirmasi, lalu kirim paksa ke cabang gh-pages (cabang khusus, sejarahnya satu commit)
#
# Yang dikirim: seluruh isi webmap/ TERMASUK webmap/data/ (peta, tile, response.json), karena git main mengabaikan webmap/data.
# Yang TIDAK tersentuh: cabang main dan semua berkas di luar webmap/. Hasil: https://<akun>.github.io/<repo>/
# Penerbitan di internet publik tidak bisa ditarik kembali sepenuhnya (bisa tersalin dan terindeks), jadi periksa dulu isinya.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

DRY=0; [[ "${1:-}" == "--dry-run" ]] && DRY=1
REMOTE="$(git remote get-url origin)"
SLUG="$(echo "$REMOTE" | sed -E 's#^(git@github.com:|https://github.com/)##; s#\.git$##')"
OWNER="${SLUG%%/*}"; REPO="${SLUG##*/}"
SITE="$(mktemp -d)"; trap 'rm -rf "$SITE"' EXIT

cp -r webmap/. "$SITE/"
touch "$SITE/.nojekyll"          # Pages tidak memproses dengan Jekyll
[[ -f "$SITE/index.html" ]] || { echo "webmap/index.html tidak ada"; exit 1; }

echo "Repo tujuan : $SLUG (cabang gh-pages)"
echo "Alamat situs: https://${OWNER}.github.io/${REPO}/"
echo "Ukuran      : $(du -sh "$SITE" | cut -f1) dalam $(find "$SITE" -type f | wc -l) berkas"
echo "Berkas terbesar (batas GitHub: peringatan 50 MB, ditolak 100 MB):"
{ find "$SITE" -type f -printf '%s %P\n' | sort -rn | head -4 | awk '{printf "  %7.1f MB  %s\n", $1/1048576, $2}'; } || true   # head menutup pipa lebih dulu (SIGPIPE) dan itu wajar
BIG="$(find "$SITE" -type f -size +95M | head -1 || true)"
[[ -n "$BIG" ]] && { echo "GALAT: ada berkas di atas 95 MB (${BIG#$SITE/}); GitHub akan menolaknya."; exit 1; }

if [[ $DRY -eq 1 ]]; then echo "(dry-run: tidak ada yang dikirim)"; exit 0; fi

echo
echo "Ini akan MENERBITKAN isi di atas ke internet publik dan menimpa cabang gh-pages."
read -r -p "Lanjut? ketik 'ya': " ANS
[[ "$ANS" == "ya" ]] || { echo "Dibatalkan."; exit 1; }

NAME="$(git config user.name)"; MAIL="$(git config user.email)"
cd "$SITE"
git init -q -b gh-pages
git add -A
git -c user.name="$NAME" -c user.email="$MAIL" commit -q -m "Terbitkan webmap $(date '+%F %H:%M')"
git remote add origin "$REMOTE"
git push --force origin gh-pages
echo
echo "Selesai. Aktifkan sekali di GitHub: Settings > Pages > Source: Deploy from a branch > gh-pages / (root)."
echo "Situs: https://${OWNER}.github.io/${REPO}/"
