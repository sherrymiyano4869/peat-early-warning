"""Pilih klaster stasiun terbaik untuk pilot.

    python scripts/pick_pilot.py [--min-days 14] [--eps 0.25] [--min-stations 3]
Masuk : data/interim/stations.parquet (hasil 01_stations)
Keluar: data/interim/pilot_candidates.csv dan ringkasan di layar.
Klaster = stasiun berkoordinat wajar dengan data cukup, dikelompokkan berdasarkan jarak (derajat).
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
from sklearn.cluster import DBSCAN

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import path  # noqa: E402
from src.regions import add_region  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--min-days", type=float, default=14)
    parser.add_argument("--eps", type=float, default=0.25, help="jarak klaster dalam derajat (~28 km)")
    parser.add_argument("--keep-other-regions", action="store_true", help="jangan keluarkan stasiun di luar pulau gambut utama")
    parser.add_argument("--min-stations", type=int, default=3)
    args = parser.parse_args()

    st = add_region(pd.read_parquet(path("interim") / "stations.parquet"))
    region_ok = st["region_ok"] if not args.keep_other_regions else True
    flat = st["flat_sensor"] if "flat_sensor" in st else False
    ok = st[st.coord_ok & region_ok & ~flat & (st.days_30min >= args.min_days) & (st.wl_valid_frac >= 0.9)].copy()
    print(f"stasiun memenuhi syarat: {len(ok)} dari {len(st)} (>= {args.min_days} hari, >= 90% valid, koordinat wajar di Sumatra/Kalimantan/Papua, bukan sensor datar)")
    if ok.empty:
        sys.exit("Tidak ada stasiun yang memenuhi syarat; longgarkan --min-days.")

    ok["cluster"] = DBSCAN(eps=args.eps, min_samples=2).fit_predict(ok[["lon", "lat"]])
    rows = []
    for cid, g in ok[ok.cluster >= 0].groupby("cluster"):
        rows.append({
            "cluster": cid, "n_stasiun": len(g),
            "wilayah": g.region.mode().iat[0], "lon_tengah": round(g.lon.mean(), 3), "lat_tengah": round(g.lat.mean(), 3),
            "bbox": f"{g.lon.min() - 0.1:.2f},{g.lat.min() - 0.1:.2f},{g.lon.max() + 0.1:.2f},{g.lat.max() + 0.1:.2f}",
            "hari_median": round(g.days_30min.median(), 1), "riwayat_harian_median": int(g.n_daily.median()),
            "wl_median_cm": round(g.wl_median_cm.median(), 0),
        })
    table = pd.DataFrame(rows).sort_values(["n_stasiun", "hari_median"], ascending=False)
    print("\n== Klaster (urut jumlah stasiun)")
    print(table.to_string(index=False))
    print(f"\nStasiun tunggal (tanpa klaster): {int((ok.cluster < 0).sum())}")
    if table.empty or table.n_stasiun.max() < args.min_stations:
        print(f"Catatan: tidak ada klaster dengan >= {args.min_stations} stasiun; coba --eps lebih besar.")

    out = path("interim") / "pilot_candidates.csv"
    ok[["station_id", "name", "lon", "lat", "days_30min", "n_daily", "wl_median_cm", "cluster"]].sort_values(
        ["cluster", "station_id"]).to_csv(out, index=False)
    print("Tersimpan:", out)


if __name__ == "__main__":
    main()
