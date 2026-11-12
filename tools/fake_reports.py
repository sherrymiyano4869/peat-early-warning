"""fake_reports: laporan lapangan TIRUAN (bentuk ekspor CSV Kobo) untuk menguji alur 16 -> 17 -> 18 sebelum ada data nyata.

    python tools/fake_reports.py --out /tmp/laporan_tiruan.csv
    python scripts/16_ingest_reports.py --csv /tmp/laporan_tiruan.csv --source tiruan

Dibuat dari data/interim/hotspots.parquet: sebagian sel-hari VIIRS ikut "dilaporkan" (--detect), ditambah kejadian membara yang TIDAK terlihat VIIRS
beberapa hari setelah api di sel yang sama (--missed), patroli nihil, tindakan, bacaan muka air mingguan (lebih dalam bila risk_index.tif lebih tinggi,
jadi korelasi di 18 adalah buatan), sekat, dan jawaban atas daftar tugas 19 bila ada. Sumber WAJIB bernama `tiruan` agar hasil hilir ditandai.
"""
import argparse
import sys
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import path  # noqa: E402
from src.reports import KONDISI_SEKAT, TINDAKAN  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True); ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--detect", type=float, default=0.5); ap.add_argument("--missed", type=int, default=30); ap.add_argument("--nihil", type=int, default=200)
    ap.add_argument("--water-points", type=int, default=25); ap.add_argument("--sekat", type=int, default=15)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    hot = pd.read_parquet(path("interim") / "hotspots.parquet")
    days = pd.date_range(hot["date"].min(), hot["date"].max(), freq="D")
    box = hot["lon"].min(), hot["lon"].max(), hot["lat"].min(), hot["lat"].max()
    rows = []

    def add(lon, lat, day, jenis, pelapor=None, **extra):
        seen = pd.Timestamp(day) + pd.Timedelta(hours=float(rng.uniform(1, 11)))     # UTC; 08-18 WIB
        pelapor = pelapor or rng.choice(["warga", "mpa", "desa", "bpbd", "manggala_agni"], p=[0.45, 0.25, 0.1, 0.1, 0.1])
        rows.append({"_uuid": str(uuid.UUID(int=int(rng.integers(0, 2**63)))), "_submission_time": (seen + pd.Timedelta(hours=float(rng.exponential(6)))).isoformat(),
                     "waktu_amat": seen.isoformat() + "Z", "lokasi": f"{lat:.6f} {lon:.6f} 0 {rng.choice([5, 8, 12, 80], p=[0.4, 0.3, 0.2, 0.1])}",
                     "jenis": jenis, "pelapor": pelapor, "kode_pelapor": f"P{rng.integers(1, 40):02d}", "foto": "foto.jpg" if rng.random() < 0.7 else "", **extra})

    jitter = lambda: rng.normal(0, 0.002, 2)
    cells = hot.groupby(["cell_id", "date"]).agg(lon=("lon", "mean"), lat=("lat", "mean")).reset_index()
    for r in cells[rng.random(len(cells)) < args.detect].itertuples():
        dx, dy = jitter()
        add(r.lon + dx, r.lat + dy, r.date, rng.choice(["api", "asap"], p=[0.7, 0.3]))
    for r in cells.sample(n=min(args.missed, len(cells)), random_state=args.seed).itertuples():
        dx, dy = jitter()
        add(r.lon + dx + 0.03, r.lat + dy, r.date + pd.Timedelta(days=int(rng.integers(4, 9))), "membara")      # > 1 km dan > 48 jam dari deteksi asal
    for _ in range(args.nihil):
        add(rng.uniform(*box[:2]), rng.uniform(*box[2:]), rng.choice(days), "nihil")
    for r in cells.sample(n=min(20, len(cells)), random_state=args.seed + 1).itertuples():
        add(r.lon, r.lat, r.date, "tindakan", pelapor="manggala_agni", jenis_tindakan=rng.choice(list(TINDAKAN)))

    lon_w, lat_w = rng.uniform(*box[:2], args.water_points), rng.uniform(*box[2:], args.water_points)
    idx, risk = rng.random(args.water_points), path("features") / "grid" / "risk_index.tif"
    if risk.exists():
        import rasterio
        from pyproj import Transformer
        with rasterio.open(risk) as src:
            x, y = Transformer.from_crs(4326, src.crs, always_xy=True).transform(lon_w, lat_w)
            v = np.array([s[0] for s in src.sample(zip(x, y))], dtype=float)
        idx = np.where(np.isfinite(v), v, idx)
    for i in range(args.water_points):
        for day in days[::7]:
            add(lon_w[i], lat_w[i], day, "muka_air", kedalaman_cm=round(float(15 + 70 * idx[i] + rng.normal(0, 12)), 1), titik_acuan=f"SP{i + 1:02d}")
    for i in range(args.sekat):
        add(rng.uniform(*box[:2]), rng.uniform(*box[2:]), rng.choice(days), "sekat", kondisi_sekat=rng.choice(list(KONDISI_SEKAT)), titik_acuan=f"SK{i + 1:02d}")

    task_dir = path("outputs") / "tugas"
    burning = set(zip(cells["cell_id"], cells["date"]))
    for f in sorted(task_dir.glob("tugas_*.parquet")) if task_dir.exists() else []:
        for t in pd.read_parquet(f).itertuples():
            if rng.random() < 0.7:
                day = pd.Timestamp(t.issue_date) + pd.Timedelta(days=1)
                fire = any((t.cell_id, day + pd.Timedelta(days=k)) in burning for k in range(3))
                add(t.lon, t.lat, day, "api" if fire else "nihil", pelapor="mpa", id_tugas=t.id_tugas)

    pd.DataFrame(rows).to_csv(args.out, index=False)
    print(f"{args.out}: {len(rows)} laporan TIRUAN | {pd.Series([r['jenis'] for r in rows]).value_counts().to_dict()}")


if __name__ == "__main__":
    main()
