"""03_assemble: gabungkan target muka air harian dengan fitur GEE menjadi satu tabel model.

    python scripts/03_assemble.py [--min-target-days 30] [--eps 0.25]

Masuk : data/interim/{ts_30min,ts_daily,stations}.parquet dan data/features/gee_*.parquet (yang ada saja)
Keluar: data/features/model_table.parquet (satu baris per stasiun-hari) dan model_table_dictionary.csv

Target harian `wl_cm`: median harian dari data 30 menitan (bila >= 24 titik), selain itu nilai harian dari
`history`. Fitur hanya memakai informasi sampai hari t (tanpa kebocoran):
  - hujan: jumlah 7/14/30 hari yang berakhir pada t dan jumlah hari kering beruntun
  - Sentinel-1/2: komposit terbaru yang jendelanya sudah berakhir pada atau sebelum t
ENSO tidak dimasukkan: dalam jendela beberapa bulan nilainya nyaris konstan; baru bermakna pada data multi-tahun.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import path  # noqa: E402
from src.regions import add_region  # noqa: E402

WL_RANGE = (-400.0, 100.0)


def daily_target(ts30: pd.DataFrame, daily: pd.DataFrame, min_points: int = 24) -> pd.DataFrame:
    t = ts30.assign(date=ts30["ts_local"].dt.normalize())
    g = t.groupby(["station_id", "date"]).agg(wl_cm=("water_level_cm", "median"), n=("water_level_cm", "count")).reset_index()
    g = g[g["n"] >= min_points][["station_id", "date", "wl_cm"]].assign(src="30min")
    h = daily.dropna(subset=["water_level_cm"]).rename(columns={"water_level_cm": "wl_cm"})[["station_id", "date", "wl_cm"]]
    h = h[h["wl_cm"].between(*WL_RANGE)].assign(date=lambda x: x["date"].dt.normalize(), src="hist")
    both = pd.concat([g, h], ignore_index=True).sort_values(["station_id", "date", "src"])  # "30min" < "hist"
    return both.drop_duplicates(["station_id", "date"], keep="first").reset_index(drop=True)


def add_clusters(st: pd.DataFrame, eps: float) -> pd.DataFrame:
    st = st.copy()
    labels = DBSCAN(eps=eps, min_samples=2).fit_predict(st[["lon", "lat"]])
    singles = iter(range(1000, 1000 + len(st)))
    st["cluster"] = [lab if lab >= 0 else next(singles) for lab in labels]  # stasiun tunggal = klaster sendiri
    return st


def rain_features(chirps: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for sid, g in chirps.groupby("station_id"):
        s = g.set_index("date")["rain_mm"].sort_index().asfreq("D")
        f = pd.DataFrame(index=s.index)
        for w in (7, 14, 30):
            f[f"rain_{w}d"] = s.rolling(w, min_periods=w).sum()
        dry = (s < 1.0).astype(float).where(s.notna())
        f["dry_days"] = dry.groupby((dry == 0).cumsum()).cumsum()
        f["station_id"] = sid
        parts.append(f.reset_index())
    return pd.concat(parts, ignore_index=True)[["station_id", "date", "rain_7d", "rain_14d", "rain_30d", "dry_days"]]


def report_rain_agreement(gsmap: pd.DataFrame, chirps: pd.DataFrame) -> None:
    both = gsmap.merge(chirps, on=["station_id", "date"], suffixes=("_gsmap", "_chirps")).dropna()
    if len(both) < 30:
        return
    corr = both["rain_mm_gsmap"].corr(both["rain_mm_chirps"])
    ratio = both["rain_mm_gsmap"].sum() / max(both["rain_mm_chirps"].sum(), 1e-9)
    print(f"[hujan] gsmap vs chirps pada {len(both)} stasiun-hari: korelasi harian {corr:.2f}, rasio total gsmap/chirps {ratio:.2f}")


def merge_composite(df: pd.DataFrame, comp: pd.DataFrame, tolerance_days: int = 24) -> pd.DataFrame:
    comp = comp.drop(columns=["window_start"]).sort_values("window_end")
    merged = pd.merge_asof(df.sort_values("date"), comp, left_on="date", right_on="window_end", by="station_id",
                           direction="backward", tolerance=pd.Timedelta(days=tolerance_days))
    return merged.drop(columns=["window_end"]).sort_values(["station_id", "date"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--min-target-days", type=int, default=30)
    parser.add_argument("--eps", type=float, default=0.25, help="jarak klaster (derajat)")
    parser.add_argument("--rain-source", choices=["auto", "gsmap", "chirps"], default="auto",
                        help="auto = gsmap bila ada (lebih mutakhir), selain itu chirps")
    parser.add_argument("--keep-other-regions", action="store_true", help="jangan keluarkan stasiun di luar Sumatra/Kalimantan/Papua")
    parser.add_argument("--keep-flat", action="store_true", help="jangan keluarkan sensor datar di sekitar nol")
    args = parser.parse_args()

    interim, feats = path("interim"), path("features")
    st = add_region(pd.read_parquet(interim / "stations.parquet"))
    target = daily_target(pd.read_parquet(interim / "ts_30min.parquet"), pd.read_parquet(interim / "ts_daily.parquet"))

    n_days = target.groupby("station_id")["date"].nunique()
    keep = st[st["coord_ok"] & st["station_id"].isin(n_days[n_days >= args.min_target_days].index)]
    if not args.keep_other_regions:
        outside = keep[~keep["region_ok"]]["station_id"].tolist()
        keep = keep[keep["region_ok"]]
        if outside:
            print(f"di luar Sumatra/Kalimantan/Papua dikeluarkan: {outside}")
    if "flat_sensor" in keep and not args.keep_flat:
        dropped = keep[keep["flat_sensor"]]["station_id"].tolist()
        keep = keep[~keep["flat_sensor"]]
        if dropped:
            print(f"sensor datar dikeluarkan: {dropped}")
    print(f"stasiun lolos (koordinat wajar, >= {args.min_target_days} hari target): {len(keep)} dari {len(st)}")
    if keep.empty:
        sys.exit("Tidak ada stasiun yang lolos; turunkan --min-target-days.")
    keep = add_clusters(keep, args.eps)
    df = target.merge(keep[["station_id", "lon", "lat", "region", "cluster"]], on="station_id", how="inner")

    rain_files = {n: feats / f"gee_{n}.parquet" for n in ("gsmap", "chirps")}
    available = [n for n, f in rain_files.items() if f.exists()]
    if len(available) == 2:
        report_rain_agreement(*(pd.read_parquet(rain_files[n]) for n in ("gsmap", "chirps")))
    source = (available[0] if available else None) if args.rain_source == "auto" else args.rain_source
    if source and not rain_files[source].exists():
        sys.exit(f"--rain-source {source} dipilih, tetapi {rain_files[source].name} tidak ada.")

    for name in ("static", "rain", "s1", "s2"):
        file = feats / (f"gee_{source}.parquet" if name == "rain" and source else f"gee_{name}.parquet")
        if not file.exists():
            print(f"[{name}] tidak ada ({file.name}); dilewati")
            continue
        extra = pd.read_parquet(file)
        if name == "static":
            df = df.merge(extra, on="station_id", how="left")
        elif name == "rain":
            rf = rain_features(extra)
            print(f"[hujan] sumber {source}: data terakhir {extra['date'].max().date()}")
            df = df.merge(rf, on=["station_id", "date"], how="left")
        else:
            df = merge_composite(df, extra)
        print(f"[{name}] digabung ({len(extra)} baris)")

    df = df.sort_values(["station_id", "date"]).reset_index(drop=True)
    df.to_parquet(feats / "model_table.parquet", index=False)

    dictionary = {
        "wl_cm": "muka air harian (cm; negatif = di bawah permukaan), target", "src": "sumber nilai harian: 30min atau hist",
        "cluster": "klaster spasial (stasiun tunggal = klaster sendiri)", "region": "pulau: sumatra, kalimantan, atau papua", "elev_m": "elevasi Copernicus GLO30 (m)",
        "slope_deg": "kemiringan (derajat)", "rain_7d": "hujan CHIRPS 7 hari berakhir di t (mm)",
        "rain_14d": "hujan 14 hari (mm)", "rain_30d": "hujan 30 hari (mm)", "dry_days": "hari kering beruntun (<1 mm) sampai t",
        "vv": "Sentinel-1 VV (dB) komposit terbaru", "vh": "Sentinel-1 VH (dB)", "ndmi": "NDMI Sentinel-2 komposit terbaru",
    }
    pd.DataFrame([{"kolom": c, "keterangan": dictionary.get(c, "")} for c in df.columns]).to_csv(
        feats / "model_table_dictionary.csv", index=False)

    print(f"\nmodel_table: {len(df)} baris | {df['station_id'].nunique()} stasiun | {df['cluster'].nunique()} klaster | wilayah {df.groupby('region')['station_id'].nunique().to_dict()} "
          f"| {df['date'].min().date()} .. {df['date'].max().date()}")
    cols = [c for c in dictionary if c in df.columns and c not in ("wl_cm", "src", "cluster", "region")]
    print("terisi (%):", {c: round(100 * df[c].notna().mean()) for c in cols})
    print("Tersimpan di", feats)


if __name__ == "__main__":
    main()
