"""19_verification_tasks: daftar tugas pemeriksaan lapangan dari prediksi terbit terakhir (jalankan setelah 14, tiap kali prediksi terbit).

    python scripts/19_verification_tasks.py [--n-top 20 --n-random 5 --watch-days 14]

Masuk : outputs/fire_prob_latest.parquet (14); opsional data/features/event_ledger.parquet (17)
Keluar: outputs/tugas/tugas_<tanggal_terbit>.parquet   catatan lengkap: id_tugas, sel, alasan, peringkat, peluang, peluang_terpilih (untuk 18)
        outputs/verification_tasks.geojson             untuk pemeriksa: HANYA id_tugas dan lokasi, urutan diacak

Tiga alasan tugas:
  teratas        --n-top sel berpeluang tertinggi (horizon pertama)
  acak           --n-random sel dipilih acak merata dari sel LAIN. Tanpa ini sel berisiko tinggi saja yang diperiksa (bias verifikasi)
                 dan kejadian yang luput dari model tidak pernah terukur. peluang_terpilih disimpan agar bisa dibobot balik
  pantauan_sisa  sel dengan kejadian di buku besar dalam --watch-days hari terakhir (kandidat membara sisa), bila belum termasuk teratas
Pemeriksa tidak diberi tahu alasan atau peluangnya, supaya hasil periksa tidak terpengaruh. Pemeriksa mengisi id_tugas di formulir laporan
(jenis `nihil` bila tidak ada apa-apa). Pilihan acak ditentukan oleh tanggal terbit, jadi menjalankan ulang memberi daftar yang sama.
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import path  # noqa: E402
from src.grid import cell_polygon_lonlat  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n-top", type=int, default=20); ap.add_argument("--n-random", type=int, default=5); ap.add_argument("--watch-days", type=int, default=14)
    args = ap.parse_args()
    outputs = path("outputs")
    prob_file = outputs / "fire_prob_latest.parquet"
    if not prob_file.exists():
        sys.exit(f"{prob_file} tidak ada. Jalankan 14_fire_model.py dulu.")
    prob = pd.read_parquet(prob_file).sort_values("rank").reset_index(drop=True)
    issue = pd.Timestamp(prob["issue_date"].iloc[0])
    p_col = next(c for c in prob.columns if c.startswith("p") and c[1:].isdigit())

    top = prob.head(args.n_top).assign(alasan="teratas", peluang_terpilih=1.0)
    rest = prob.iloc[args.n_top:]
    n_rand = min(args.n_random, len(rest))
    rand = rest.sample(n=n_rand, random_state=int(issue.strftime("%Y%m%d"))).assign(alasan="acak", peluang_terpilih=n_rand / max(len(rest), 1))
    parts = [top, rand]
    led_file = path("features") / "event_ledger.parquet"
    if led_file.exists() and args.watch_days > 0:
        led = pd.read_parquet(led_file, columns=["cell_id", "date", "status"])
        recent = led[(led["status"] == "kejadian") & (led["date"] <= issue) & (led["date"] > issue - pd.Timedelta(days=args.watch_days))]
        taken = pd.concat(parts)["cell_id"]
        parts.append(prob[prob["cell_id"].isin(recent["cell_id"]) & ~prob["cell_id"].isin(taken)].assign(alasan="pantauan_sisa", peluang_terpilih=1.0))
    tasks = pd.concat(parts, ignore_index=True)
    tasks = tasks.sample(frac=1, random_state=int(issue.strftime("%Y%m%d")) + 1).reset_index(drop=True)      # urutan id tidak membocorkan alasan
    tasks.insert(0, "id_tugas", [f"T{issue:%Y%m%d}-{i:03d}" for i in range(1, len(tasks) + 1)])
    tasks = tasks[["id_tugas", "issue_date", "cell_id", "cx", "cy", "lon", "lat", "alasan", "rank", p_col, "peluang_terpilih"]]

    (outputs / "tugas").mkdir(exist_ok=True)
    tasks.to_parquet(outputs / "tugas" / f"tugas_{issue.date()}.parquet", index=False)
    feats = [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [cell_polygon_lonlat(int(r.cx), int(r.cy))]},
              "properties": {"id_tugas": r.id_tugas, "lon": round(float(r.lon), 5), "lat": round(float(r.lat), 5)}} for r in tasks.itertuples()]
    (outputs / "verification_tasks.geojson").write_text(json.dumps({"type": "FeatureCollection", "issue_date": str(issue.date()), "features": feats}, ensure_ascii=False))
    print(f"tugas terbit {issue.date()}: {tasks['alasan'].value_counts().to_dict()} -> outputs/tugas/tugas_{issue.date()}.parquet, outputs/verification_tasks.geojson")


if __name__ == "__main__":
    main()
