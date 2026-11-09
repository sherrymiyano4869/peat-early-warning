"""archive_run: simpan jejak ringan dari satu run, untuk perbandingan antarminggu dan penilaian prospektif.

    python scripts/archive_run.py [--label teks] [--include-web]

Menyalin ke outputs/arsip/<YYYYMMDD_HHMMSSZ>/ (tidak pernah menimpa arsip lain) :
  predictions_<tanggal_terbit>.csv   prediksi yang BENAR-BENAR diterbitkan (kelak dinilai terhadap kenyataan)
  metrics_*.csv, walkforward_*.csv   metrik run itu
  run_meta.json                      waktu, versi kode, commit git, data sampai kapan, jumlah stasiun, ringkasan validasi
  manifest.json, stations.geojson    dari webmap/data (--include-web: seluruh folder, termasuk hamparan dan deret waktu)
Dan menambah satu baris di outputs/arsip/index.csv. Yang diarsipkan sengaja kecil; data mentah sudah bertanggal (01a, 01b).
Tujuan utama: arsip prediksi menjadi uji prospektif (apa yang dikatakan model sebelum kenyataan datang), bukan simulasi mundur.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import ROOT, path  # noqa: E402


def version() -> str:
    f = ROOT / "CHANGELOG.md"
    m = re.search(r"^##\s+(v[\d.]+)", f.read_text(encoding="utf-8"), re.M) if f.exists() else None
    return m.group(1) if m else "dev"


def git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", default="", help="catatan bebas untuk run ini")
    parser.add_argument("--include-web", action="store_true", help="salin seluruh webmap/data, bukan hanya manifest dan stations.geojson")
    args = parser.parse_args()

    outputs, feats = path("outputs"), path("features")
    now = datetime.now(timezone.utc)
    base = outputs / "arsip" / now.strftime("%Y%m%d_%H%M%SZ")
    dest, k = base, 1
    while dest.exists():  # jangan menimpa arsip run lain yang dibuat pada detik yang sama
        k += 1
        dest = Path(f"{base}_{k}")
    dest.mkdir(parents=True)
    copied = []

    issue = None
    pred_file = outputs / "predictions_latest.csv"
    if pred_file.exists():
        pred = pd.read_csv(pred_file, parse_dates=["issue_date"])
        issue = str(pred["issue_date"].max().date())
        shutil.copy2(pred_file, dest / f"predictions_{issue}.csv")
        copied.append(f"predictions_{issue}.csv")
    for pattern in ("metrics_*.csv", "walkforward_*.csv"):
        for f in sorted(outputs.glob(pattern)):
            shutil.copy2(f, dest / f.name)
            copied.append(f.name)

    web = ROOT / "webmap" / "data"
    if web.exists():
        if args.include_web:
            shutil.copytree(web, dest / "webmap_data", dirs_exist_ok=True)
            copied.append("webmap_data/")
        else:
            for name in ("manifest.json", "stations.geojson"):
                if (web / name).exists():
                    shutil.copy2(web / name, dest / name)
                    copied.append(name)

    meta = {"run_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "version": version(), "git": git_commit(), "label": args.label,
            "issue_date": issue, "files": copied}
    mt = feats / "model_table.parquet"
    if mt.exists():
        df = pd.read_parquet(mt, columns=["station_id", "date"])
        meta.update(data_through=str(df["date"].max().date()), n_rows=int(len(df)), n_stations=int(df["station_id"].nunique()))
    wf = outputs / "walkforward_summary.csv"
    if wf.exists():
        sm = pd.read_csv(wf).set_index("horizon")
        meta["validation"] = {f"h{int(h)}": {"skill_vs_persistensi": float(sm.loc[h, "skill_vs_persistensi"]),
                                             "cakupan_q10_q90": float(sm.loc[h, "cakupan_q10_q90"])} for h in sm.index}
    (dest / "run_meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")

    index = outputs / "arsip" / "index.csv"
    v = meta.get("validation", {})
    row = {"folder": dest.name, "run_utc": meta["run_utc"], "issue_date": issue, "data_through": meta.get("data_through"),
           "version": meta["version"], "git": meta["git"], "skill_h7": v.get("h7", {}).get("skill_vs_persistensi"),
           "skill_h14": v.get("h14", {}).get("skill_vs_persistensi"), "cakupan_h7": v.get("h7", {}).get("cakupan_q10_q90"), "label": args.label}
    pd.concat([pd.read_csv(index), pd.DataFrame([row])], ignore_index=True).to_csv(index, index=False) if index.exists() \
        else pd.DataFrame([row]).to_csv(index, index=False)
    print(f"arsip: {dest} | {len(copied)} berkas | terbit {issue} | data sampai {meta.get('data_through')} | {meta['version']} {meta['git']}")


if __name__ == "__main__":
    main()
