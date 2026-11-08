#!/usr/bin/env bash
# Pasang lingkungan 'peat' di WSL (Ubuntu). Jalankan dari folder proyek:
#   bash setup_env.sh
set -euo pipefail

if command -v mamba >/dev/null 2>&1; then
  SOLVER=mamba
elif command -v conda >/dev/null 2>&1; then
  SOLVER=conda
else
  echo "conda belum ada. Memasang Miniforge (conda-forge) ke ~/miniforge3 ..."
  curl -L -o /tmp/miniforge.sh \
    "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh"
  bash /tmp/miniforge.sh -b -p "$HOME/miniforge3"
  # shellcheck disable=SC1091
  source "$HOME/miniforge3/etc/profile.d/conda.sh"
  "$HOME/miniforge3/bin/conda" init bash >/dev/null
  SOLVER=conda
fi

if "$SOLVER" env list | grep -qE '^peat\s'; then
  echo "Lingkungan 'peat' sudah ada. Memperbarui ..."
  "$SOLVER" env update -n peat -f environment.yml --prune
else
  echo "Membuat lingkungan 'peat' (unduhan besar, sekitar 650 MB) ..."
  "$SOLVER" env create -f environment.yml
fi

echo "Mendaftarkan kernel Jupyter ..."
"$SOLVER" run -n peat python -m ipykernel install --user --name peat --display-name "Python (peat)"

echo "Memeriksa ..."
"$SOLVER" run -n peat python scripts/check_env.py

cat <<MSG

Selesai. Berikutnya:
  conda activate peat      (buka terminal baru jika conda baru dipasang)
  earthengine authenticate --quiet
  # isi gee.project di config.yaml, lalu:
  python scripts/00_setup.py
MSG
