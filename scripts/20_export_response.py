"""20_export_response: ekspor buku besar, tugas pemeriksaan, sekat, muka air lapangan, dan skor ke webmap/data/response.json (halaman Respons).

    python scripts/20_export_response.py [--days 90] [--out webmap/data]
    python -m http.server -d webmap 8000        # lalu buka http://localhost:8000/response.html

Masuk : data/features/event_ledger.parquet (17); opsional outputs/tugas/*.parquet (19), data/interim/reports.parquet (16), data/features/canal_blocks.parquet (17),
        outputs/prospective_scores.json (18), outputs/fire_top_cells.geojson (14), data/interim/ledger_meta.json (17)
Keluar: webmap/data/response.json (satu berkas; halaman Respons tidak bergantung pada manifest.json dari 09)

Privasi: titik laporan kejadian TIDAK diekspor, hanya sel 1 km; kode pelapor tidak diekspor. Titik sekat dan titik muka air diekspor karena itu
lokasi sarana, bukan lokasi orang. Alasan tugas (teratas, acak, pantauan sisa) tidak diekspor per tugas agar pemeriksa tetap buta; hanya ringkasan 18.
Hanya --days hari terakhir buku besar yang diekspor (sampai tanggal terakhirnya).
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import ROOT, load_config, path  # noqa: E402
from src.grid import cell_from_id, cell_polygon_lonlat  # noqa: E402
from src.reports import KEJADIAN  # noqa: E402

LEDGER_COLS = ["cell_id", "status", "sumber", "tingkat", "n_viirs", "n_match", "n_pos", "n_nihil", "n_kunjungan", "n_tindakan", "membara", "menyala", "konflik"]


def read_json(f: Path):
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "webmap" / "data")); ap.add_argument("--days", type=int, default=90)
    args = ap.parse_args()
    feats, interim, outputs = path("features"), path("interim"), path("outputs")
    led_file = feats / "event_ledger.parquet"
    if not led_file.exists():
        sys.exit(f"{led_file} tidak ada. Jalankan 17_event_ledger.py dulu.")
    led = pd.read_parquet(led_file)
    date_max = led["date"].max()
    led = led[led["date"] > date_max - pd.Timedelta(days=args.days)]
    rows = led[LEDGER_COLS].assign(date=led["date"].dt.strftime("%Y-%m-%d")).to_dict("records")

    tasks, task_issue = [], None
    task_files = sorted((outputs / "tugas").glob("tugas_*.parquet")) if (outputs / "tugas").exists() else []
    rep = pd.read_parquet(interim / "reports.parquet") if (interim / "reports.parquet").exists() else None
    if task_files:
        t = pd.read_parquet(task_files[-1])
        task_issue = str(pd.Timestamp(t["issue_date"].iloc[0]).date())
        done = rep[rep["id_tugas"].notna() & rep["jenis"].isin(KEJADIAN + ("nihil",))].assign(k=lambda d: d["jenis"].isin(KEJADIAN)).groupby("id_tugas")["k"].max() if rep is not None else pd.Series(dtype=bool)
        hasil = t["id_tugas"].map(done).map({True: "kejadian", False: "nihil"}).fillna("belum")
        tasks = [{"id_tugas": i, "cell_id": int(c), "hasil": h} for i, c, h in zip(t["id_tugas"], t["cell_id"], hasil)]

    top = read_json(outputs / "fire_top_cells.geojson")
    water = []
    if rep is not None:
        w = rep[rep["jenis"] == "muka_air"].sort_values("observed_utc")
        w = w.assign(titik=w["titik_acuan"].fillna(w["lon"].round(3).astype(str) + "_" + w["lat"].round(3).astype(str)))
        g = w.groupby("titik").agg(lon=("lon", "median"), lat=("lat", "median"), muka_air_cm=("muka_air_cm", "last"), tanggal=("date", "last"), n=("jenis", "size")).reset_index()
        water = [{"titik": r.titik, "lon": round(r.lon, 5), "lat": round(r.lat, 5), "muka_air_cm": round(float(r.muka_air_cm), 1), "tanggal": str(r.tanggal.date()), "n": int(r.n)} for r in g.itertuples()]
    sekat = []
    if (feats / "canal_blocks.parquet").exists():
        s = pd.read_parquet(feats / "canal_blocks.parquet")
        sekat = [{"titik": r.titik, "lon": round(r.lon, 5), "lat": round(r.lat, 5), "kondisi": r.kondisi, "tanggal": str(r.tanggal.date()), "n": int(r.n_laporan)} for r in s.itertuples()]

    ids = sorted(set(led["cell_id"]) | {t["cell_id"] for t in tasks})
    cx, cy = cell_from_id(ids)
    cells = {str(i): cell_polygon_lonlat(int(a), int(b)) for i, a, b in zip(ids, cx, cy)}
    for r in rows:
        r["cell_id"] = str(r["cell_id"])
    for t in tasks:
        t["cell_id"] = str(t["cell_id"])
    changelog = ROOT / "CHANGELOG.md"
    version = next((ln.split()[1] for ln in changelog.read_text(encoding="utf-8").splitlines() if ln.startswith("## v")), "dev") if changelog.exists() else "dev"
    res = {"version": version, "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "tiruan": bool(led["tiruan"].any()),
           "date_min": str(led["date"].min().date()), "date_max": str(date_max.date()), "basemap": (load_config().get("webmap") or {}).get("basemap"),
           "parameter": (read_json(interim / "ledger_meta.json") or {}).get("parameter"), "cells": cells, "ledger": rows,
           "tasks": {"issue_date": task_issue, "items": tasks}, "top_cells": top, "water": water, "sekat": sekat, "scores": read_json(outputs / "prospective_scores.json")}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "response.json").write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    print(f"{out / 'response.json'}: {len(rows):,} sel-hari ({res['date_min']} s/d {res['date_max']}) di {len(cells):,} sel | tugas {len(tasks)} (terbit {task_issue}) | "
          f"sekat {len(sekat)} | titik muka air {len(water)} | skor {'ada' if res['scores'] else 'belum'}{' | DATA TIRUAN' if res['tiruan'] else ''}")


if __name__ == "__main__":
    main()
