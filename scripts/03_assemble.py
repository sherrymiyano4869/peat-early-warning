"""03_assemble: gabungkan target muka air harian dengan fitur GEE menjadi satu tabel model.

    python scripts/03_assemble.py [--min-target-days 30] [--max-jump-p95 30] [--smooth-days 1]

Masuk : data/interim/{ts_30min,ts_daily,stations}.parquet dan data/features/gee_*.parquet (yang ada saja)
Keluar: data/features/model_table.parquet (satu baris per stasiun-hari) dan model_table_dictionary.csv

Target harian `wl_cm`: median harian dari data 30 menitan (bila >= 24 titik), selain itu nilai harian dari
`history`. Fitur hanya memakai informasi sampai hari t (tanpa kebocoran):
  - hujan: jumlah 7/14/30 hari yang berakhir pada t dan jumlah hari kering beruntun
  - Sentinel-1/2: komposit terbaru yang jendelanya sudah berakhir pada atau sebelum t
  - tren muka air: perubahan 3 dan 7 hari terakhir (`wl_d3`, `wl_d7`; hanya untuk stasiun yang terpantau)
QC: stasiun dengan lonjakan harian tak wajar dikeluarkan (persentil 95 |perubahan 1 hari| > --max-jump-p95 cm; 0 = mati).
`fut_rain_7d`/`fut_rain_14d` adalah hujan MASA DEPAN teramati: ORACLE hanya untuk diagnosis batas atas, bukan fitur sah.
  - HTH (hari tanpa hujan, definisi BMKG: hujan < 1 mm berturut-turut): `dry_days`, kategori BMKG `dry_cat` (0 = hujan,
    1 = 1-5 hari ... 6 = > 60 hari), `dry_max_30d` (rentetan kering terpanjang 30 hari terakhir), `rain_days_30d`
  - anomali komposit satelit per stasiun (`vv_anom`, `vh_anom`, `ndmi_anom`): nilai dikurangi median berjalan stasiun itu
    (hanya komposit yang sudah selesai; min 3 komposit)
  - ENSO/IOD bulanan (`nino34`, `oni`, `dmi`) bila data/features/enso_monthly.parquet ada, memakai bulan yang sudah selesai
    (lag 1 bulan). Dalam jendela beberapa bulan nilainya nyaris konstan, jadi tidak dipakai sebagai fitur model harian secara
    bawaan; kegunaan utamanya di 05_seasonal_outlook (data multi-tahun).
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import path  # noqa: E402
from src.enso import lagged_for_dates  # noqa: E402
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


def snapshot_noise(ts30: pd.DataFrame, daily: pd.DataFrame, min_points: int = 24) -> pd.Series:
    """Simpangan baku selisih antara nilai harian `history` dan median 30 menitan pada hari yang sama, per stasiun."""
    t = ts30.assign(date=ts30["ts_local"].dt.normalize()).groupby(["station_id", "date"])["water_level_cm"].agg(["median", "count"]).reset_index()
    t = t[t["count"] >= min_points]
    h = daily.dropna(subset=["water_level_cm"]).assign(date=lambda x: x["date"].dt.normalize())[["station_id", "date", "water_level_cm"]]
    both = t.merge(h, on=["station_id", "date"])
    return (both["water_level_cm"] - both["median"]).groupby(both["station_id"]).std().dropna()


def jump_stats(target: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sid, g in target.groupby("station_id"):
        s = g.set_index("date")["wl_cm"].sort_index().asfreq("D")
        d1 = s.diff().abs()
        rows.append({"station_id": sid, "jump_p95": d1.quantile(0.95), "jump_max": d1.max(),
                     "abs_d7_median": s.diff(7).abs().median()})
    return pd.DataFrame(rows)


def smooth_target(df: pd.DataFrame, k: int) -> pd.DataFrame:
    """Median bergerak mundur (hanya data sampai t) agar tidak ada kebocoran."""
    out = []
    for sid, g in df.groupby("station_id"):
        s = g.set_index("date")["wl_cm"].sort_index().asfreq("D")
        g = g.copy()
        g["wl_cm"] = s.rolling(k, min_periods=1).median().reindex(g["date"]).to_numpy()
        out.append(g)
    return pd.concat(out, ignore_index=True)


def wl_trend_features(df: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for sid, g in df.groupby("station_id"):
        s = g.set_index("date")["wl_cm"].sort_index().asfreq("D")
        parts.append(pd.DataFrame({"station_id": sid, "date": s.index, "wl_d3": s - s.shift(3), "wl_d7": s - s.shift(7)}))
    return pd.concat(parts, ignore_index=True)


def add_clusters(st: pd.DataFrame, eps: float) -> pd.DataFrame:
    st = st.copy()
    labels = DBSCAN(eps=eps, min_samples=2).fit_predict(st[["lon", "lat"]])
    singles = iter(range(1000, 1000 + len(st)))
    st["cluster"] = [lab if lab >= 0 else next(singles) for lab in labels]  # stasiun tunggal = klaster sendiri
    return st


BMKG_HTH_BINS = [0, 5, 10, 20, 30, 60]  # batas atas kategori 1..5; > 60 = kategori 6


def hth_category(dry_days: pd.Series) -> pd.Series:
    """Kategori HTH BMKG: 0 = masih ada hujan, 1 = 1-5, 2 = 6-10, 3 = 11-20, 4 = 21-30, 5 = 31-60, 6 = > 60 hari."""
    cat = pd.cut(dry_days, bins=[-0.5, 0.5, 5, 10, 20, 30, 60, np.inf], labels=False)
    return pd.Series(cat, index=dry_days.index).astype(float)


def longest_run(x: np.ndarray) -> float:
    best = cur = 0
    for v in x:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return float(best)


def rain_features(rain: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for sid, g in rain.groupby("station_id"):
        s = g.set_index("date")["rain_mm"].sort_index().asfreq("D")
        f = pd.DataFrame(index=s.index)
        for w in (7, 14, 30):
            f[f"rain_{w}d"] = s.rolling(w, min_periods=w).sum()
        dry = (s < 1.0).astype(float).where(s.notna())
        f["dry_days"] = dry.groupby((dry == 0).cumsum()).cumsum()
        f["dry_cat"] = hth_category(f["dry_days"])
        f["dry_max_30d"] = dry.rolling(30, min_periods=30).apply(longest_run, raw=True)
        f["rain_days_30d"] = (s >= 1.0).astype(float).where(s.notna()).rolling(30, min_periods=30).sum()
        for h in (7, 14):  # ORACLE: hujan teramati pada t+1..t+h (hanya diagnosis)
            f[f"fut_rain_{h}d"] = s.rolling(h, min_periods=h).sum().shift(-h)
        f["station_id"] = sid
        parts.append(f.reset_index())
    cols = ["station_id", "date", "rain_7d", "rain_14d", "rain_30d", "dry_days", "dry_cat", "dry_max_30d", "rain_days_30d",
            "fut_rain_7d", "fut_rain_14d"]
    return pd.concat(parts, ignore_index=True)[cols]


def report_rain_agreement(gsmap: pd.DataFrame, chirps: pd.DataFrame) -> None:
    both = gsmap.merge(chirps, on=["station_id", "date"], suffixes=("_gsmap", "_chirps")).dropna()
    if len(both) < 30:
        return
    corr = both["rain_mm_gsmap"].corr(both["rain_mm_chirps"])
    ratio = both["rain_mm_gsmap"].sum() / max(both["rain_mm_chirps"].sum(), 1e-9)
    print(f"[hujan] gsmap vs chirps pada {len(both)} stasiun-hari: korelasi harian {corr:.2f}, rasio total gsmap/chirps {ratio:.2f}")


def add_composite_anomalies(comp: pd.DataFrame, min_windows: int = 3) -> pd.DataFrame:
    """Anomali terhadap median berjalan per stasiun (hanya komposit sampai jendela itu; tanpa melihat masa depan)."""
    comp = comp.sort_values(["station_id", "window_end"]).copy()
    for col in [c for c in ("vv", "vh", "ndmi") if c in comp]:
        run_med = comp.groupby("station_id")[col].transform(lambda x: x.expanding(min_periods=min_windows).median())
        comp[f"{col}_anom"] = comp[col] - run_med
    return comp


def merge_composite(df: pd.DataFrame, comp: pd.DataFrame, tolerance_days: int = 24) -> pd.DataFrame:
    comp = add_composite_anomalies(comp).drop(columns=["window_start"]).sort_values("window_end")
    merged = pd.merge_asof(df.sort_values("date"), comp, left_on="date", right_on="window_end", by="station_id",
                           direction="backward", tolerance=pd.Timedelta(days=tolerance_days))
    return merged.drop(columns=["window_end"]).sort_values(["station_id", "date"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--min-target-days", type=int, default=30)
    parser.add_argument("--eps", type=float, default=0.25, help="jarak klaster (derajat)")
    parser.add_argument("--rain-source", choices=["auto", "gsmap", "chirps"], default="auto",
                        help="auto = gsmap bila ada (lebih mutakhir), selain itu chirps")
    parser.add_argument("--max-jump-p95", type=float, default=30.0, help="batas persentil 95 |perubahan 1 hari| (cm); 0 = mati")
    parser.add_argument("--smooth-days", type=int, default=1, help="median bergerak mundur pada target (1 = mati)")
    parser.add_argument("--keep-other-regions", action="store_true", help="jangan keluarkan stasiun di luar Sumatra/Kalimantan/Papua")
    parser.add_argument("--keep-flat", action="store_true", help="jangan keluarkan sensor datar di sekitar nol")
    args = parser.parse_args()

    interim, feats = path("interim"), path("features")
    st = add_region(pd.read_parquet(interim / "stations.parquet"))
    ts30, daily = pd.read_parquet(interim / "ts_30min.parquet"), pd.read_parquet(interim / "ts_daily.parquet")
    target = daily_target(ts30, daily)

    noise = snapshot_noise(ts30, daily)
    if len(noise):
        worst = noise.sort_values(ascending=False).head(3).round(1).to_dict()
        print(f"[kebisingan] selisih nilai harian history vs median 30 menit: median stasiun {noise.median():.1f} cm | terburuk {worst}")

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

    js = jump_stats(target[target["station_id"].isin(keep["station_id"])])
    if len(js):
        print("[lonjakan] 5 stasiun terburuk menurut persentil 95 |perubahan 1 hari| (cm):")
        print(js.sort_values("jump_p95", ascending=False).head(5).round(1).to_string(index=False))
        if args.max_jump_p95 > 0:
            noisy = js[js["jump_p95"] > args.max_jump_p95]["station_id"].tolist()
            keep = keep[~keep["station_id"].isin(noisy)]
            if noisy:
                print(f"stasiun dengan lonjakan tak wajar dikeluarkan (> {args.max_jump_p95:.0f} cm/hari): {noisy}")

    print(f"stasiun lolos: {len(keep)} dari {len(st)}")
    if keep.empty:
        sys.exit("Tidak ada stasiun yang lolos; longgarkan --min-target-days atau --max-jump-p95.")
    keep = add_clusters(keep, args.eps)
    df = target.merge(keep[["station_id", "lon", "lat", "region", "cluster"]], on="station_id", how="inner")
    if args.smooth_days > 1:
        df = smooth_target(df, args.smooth_days)
        print(f"target dihaluskan: median bergerak mundur {args.smooth_days} hari")
    df = df.merge(wl_trend_features(df), on=["station_id", "date"], how="left")

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
        if extra.empty:
            print(f"[{name}] berkas kosong ({file.name}); dilewati")
            continue
        if name == "static":
            df = df.merge(extra, on="station_id", how="left")
        elif name == "rain":
            print(f"[hujan] sumber {source}: data terakhir {extra['date'].max().date()}")
            df = df.merge(rain_features(extra), on=["station_id", "date"], how="left")
        else:
            df = merge_composite(df, extra)
        print(f"[{name}] digabung ({len(extra)} baris)")

    enso_file = feats / "enso_monthly.parquet"
    if enso_file.exists():
        enso = pd.read_parquet(enso_file)
        lagged = lagged_for_dates(df["date"], enso, lag_months=1)
        for col in lagged.columns:
            df[col] = lagged[col].to_numpy()
        distinct = {c: int(df[c].round(2).nunique()) for c in lagged.columns}
        print(f"[enso] digabung (lag 1 bulan); nilai berbeda dalam jendela data: {distinct}  "
              f"(sedikit = nyaris konstan; jangan ditafsirkan sebagai pengaruh ENSO)")
    else:
        print("[enso] tidak ada (data/features/enso_monthly.parquet); jalankan 02b_enso.py bila diperlukan")

    df = df.sort_values(["station_id", "date"]).reset_index(drop=True)
    df.to_parquet(feats / "model_table.parquet", index=False)

    dictionary = {
        "wl_cm": "muka air harian (cm; negatif = di bawah permukaan), target", "src": "sumber nilai harian: 30min atau hist",
        "cluster": "klaster spasial (stasiun tunggal = klaster sendiri)", "region": "pulau: sumatra, kalimantan, atau papua",
        "wl_d3": "perubahan muka air 3 hari terakhir (cm)", "wl_d7": "perubahan muka air 7 hari terakhir (cm)",
        "elev_m": "elevasi Copernicus GLO30 (m)", "slope_deg": "kemiringan (derajat)",
        "rain_7d": "hujan 7 hari berakhir di t (mm)", "rain_14d": "hujan 14 hari (mm)", "rain_30d": "hujan 30 hari (mm)",
        "dry_days": "hari tanpa hujan beruntun (<1 mm) sampai t (HTH)", "dry_cat": "kategori HTH BMKG: 0 hujan, 1 (1-5), 2 (6-10), 3 (11-20), 4 (21-30), 5 (31-60), 6 (>60)",
        "dry_max_30d": "rentetan hari kering terpanjang dalam 30 hari terakhir", "rain_days_30d": "jumlah hari berhujan (>=1 mm) dalam 30 hari",
        "vv_anom": "anomali VV terhadap median berjalan stasiun (dB)", "vh_anom": "anomali VH (dB)", "ndmi_anom": "anomali NDMI",
        "nino34": "anomali Nino 3.4 bulanan (lag 1 bulan)", "oni": "ONI (rata-rata 3 bulan Nino 3.4; lag 1 bulan)", "dmi": "Dipole Mode Index (lag 1 bulan)",
        "fut_rain_7d": "ORACLE: hujan teramati t+1..t+7 (hanya diagnosis)", "fut_rain_14d": "ORACLE: hujan teramati t+1..t+14 (hanya diagnosis)",
        "vv": "Sentinel-1 VV (dB) komposit terbaru", "vh": "Sentinel-1 VH (dB)", "ndmi": "NDMI Sentinel-2 komposit terbaru",
    }
    pd.DataFrame([{"kolom": c, "keterangan": dictionary.get(c, "")} for c in df.columns]).to_csv(
        feats / "model_table_dictionary.csv", index=False)

    print(f"\nmodel_table: {len(df)} baris | {df['station_id'].nunique()} stasiun | {df['cluster'].nunique()} klaster "
          f"| wilayah {df.groupby('region')['station_id'].nunique().to_dict()} | {df['date'].min().date()} .. {df['date'].max().date()}")
    cols = [c for c in dictionary if c in df.columns and c not in ("wl_cm", "src", "cluster", "region", "nino34", "oni", "dmi")]
    print("terisi (%):", {c: round(100 * df[c].notna().mean()) for c in cols})
    print("Tersimpan di", feats)


if __name__ == "__main__":
    main()
