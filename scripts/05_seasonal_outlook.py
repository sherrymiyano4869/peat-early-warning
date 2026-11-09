"""05_seasonal_outlook: apakah ENSO dan IOD memprediksi tingkat kekeringan musim kemarau di lokasi stasiun?

    python scripts/05_seasonal_outlook.py [--season 7 9] [--pred-months 5 6] [--target-year 2026]

Masuk : data/features/gee_chirps_long.parquet (02_gee_features --only chirps_long) dan enso_monthly.parquet (02b_enso)
Keluar: outputs/seasonal_overview.csv, seasonal_predictions.csv, seasonal_scatter.png

Metrik musim per stasiun-tahun (default Jul-Sep): `rain_total` (mm), `hth_max` (rentetan hari tanpa hujan < 1 mm terpanjang),
`dry_frac` (bagian hari kering). Prediktor tahun itu: Nino 3.4 dan DMI rata-rata bulan-bulan sebelum musim (default Mei-Jun).
Evaluasi leave-one-year-out pada rata-rata wilayah-tahun (stasiun satu wilayah saling berkorelasi kuat, jadi sampel efektif
adalah jumlah tahun, bukan jumlah stasiun); skor mentah distandarkan memakai tahun latih saja.
Skill = 1 - MSE model / MSE klimatologi (prediksi 0). Positif = ENSO/IOD menambah informasi di luar klimatologi.
"""
import argparse
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import path  # noqa: E402
from src.regions import add_region  # noqa: E402

METRICS = ["rain_total", "hth_max", "dry_frac"]


def longest_dry_run(rain: np.ndarray) -> float:
    best = cur = 0
    for r in rain:
        cur = cur + 1 if r < 1.0 else 0
        best = max(best, cur)
    return float(best)


def season_metrics(rain: pd.DataFrame, months, min_coverage=0.9) -> pd.DataFrame:
    """Metrik musim per (stasiun, tahun); tahun dengan data kurang dari min_coverage dibuang."""
    r = rain[rain["date"].dt.month.between(months[0], months[1])].copy()
    r["year"] = r["date"].dt.year
    rows = []
    for (sid, year), g in r.groupby(["station_id", "year"]):
        g = g.sort_values("date")
        n_expected = (pd.Timestamp(year, months[1], 1) + pd.offsets.MonthEnd(0) - pd.Timestamp(year, months[0], 1)).days + 1
        if len(g) < min_coverage * n_expected:
            continue
        v = g["rain_mm"].to_numpy(float)
        rows.append({"station_id": sid, "year": year, "rain_total": np.nansum(v), "hth_max": longest_dry_run(v),
                     "dry_frac": float(np.mean(v < 1.0))})
    return pd.DataFrame(rows)


def predictors(enso: pd.DataFrame, pred_months, years) -> pd.DataFrame:
    e = enso.assign(year=enso["date"].dt.year, month=enso["date"].dt.month)
    e = e[e["month"].between(pred_months[0], pred_months[1])]
    cols = [c for c in ("nino34", "dmi") if c in e]
    return e.groupby("year")[cols].mean().reindex(years)


def fit_predict(X_train: np.ndarray, y_train: np.ndarray, X_test: np.ndarray) -> np.ndarray:
    A = np.column_stack([np.ones(len(X_train)), X_train])
    coef, *_ = np.linalg.lstsq(A, y_train, rcond=None)
    return np.column_stack([np.ones(len(X_test)), X_test]) @ coef


def loyo(M: pd.DataFrame, X: pd.DataFrame):
    """M: tahun x stasiun (satu wilayah); X: tahun x prediktor. Kembalikan z_obs, z_pred (rata-rata wilayah per tahun)."""
    years = [y for y in M.index if y in X.dropna().index]
    z_obs, z_pred = {}, {}
    for held in years:
        train = [y for y in years if y != held]
        mu, sd = M.loc[train].mean(), M.loc[train].std().replace(0, np.nan)
        z = ((M.loc[years] - mu) / sd).mean(axis=1)  # rata-rata wilayah per tahun (standardisasi dari tahun latih)
        if z.loc[train].isna().all():
            continue
        z_obs[held] = z.loc[held]
        z_pred[held] = float(fit_predict(X.loc[train].to_numpy(float), z.loc[train].to_numpy(float), X.loc[[held]].to_numpy(float))[0])
    return pd.Series(z_obs), pd.Series(z_pred)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--season", type=int, nargs=2, default=[7, 9], help="bulan awal dan akhir musim")
    parser.add_argument("--pred-months", type=int, nargs=2, default=[5, 6], help="bulan prediktor (sebelum musim)")
    parser.add_argument("--target-year", type=int, default=2026)
    parser.add_argument("--min-years", type=int, default=15)
    args = parser.parse_args()

    feats, out = path("features"), path("outputs")
    long_file, enso_file = feats / "gee_chirps_long.parquet", feats / "enso_monthly.parquet"
    if not long_file.exists() or not enso_file.exists():
        sys.exit("Butuh gee_chirps_long.parquet (02_gee_features.py --only chirps_long) dan enso_monthly.parquet (02b_enso.py).")
    rain, enso = pd.read_parquet(long_file), pd.read_parquet(enso_file)
    st = add_region(pd.read_parquet(path("interim") / "stations.parquet"))
    region_of = dict(zip(st["station_id"], st["region"]))

    sm = season_metrics(rain, args.season)
    sm["region"] = sm["station_id"].map(region_of)
    years = sorted(sm["year"].unique())
    X = predictors(enso, args.pred_months, years)
    print(f"musim bulan {args.season[0]}-{args.season[1]} | prediktor bulan {args.pred_months[0]}-{args.pred_months[1]}: {list(X.columns)} "
          f"| tahun {years[0]}..{years[-1]} ({len(years)}) | stasiun {sm.station_id.nunique()}")

    rows, preds = [], []
    groups = {r: g for r, g in sm.groupby("region") if g["station_id"].nunique() >= 2 and g["year"].nunique() >= args.min_years}
    groups["semua"] = sm
    for region, g in groups.items():
        for metric in METRICS:
            M = g.pivot(index="year", columns="station_id", values=metric).dropna(axis=1, thresh=int(0.8 * len(years)))
            valid_years = [y for y in M.index if y in X.dropna().index]
            if len(valid_years) < args.min_years or M.shape[1] < 2:
                continue
            z_obs, z_pred = loyo(M.loc[valid_years], X)
            if len(z_obs) < args.min_years:
                continue
            mse_m, mse_c = float(np.mean((z_obs - z_pred) ** 2)), float(np.mean(z_obs ** 2))
            zfull = ((M - M.mean()) / M.std().replace(0, np.nan)).mean(axis=1)
            row = {"region": region, "metric": metric, "n_years": len(z_obs), "n_stations": M.shape[1],
                   "skill_loyo": 1 - mse_m / mse_c, "rmse_model": mse_m ** 0.5, "rmse_clim": mse_c ** 0.5}
            for col in X.columns:
                row[f"corr_{col}"] = float(zfull.reindex(X.dropna().index).corr(X[col]))
            rows.append(row)
            preds.append(pd.DataFrame({"region": region, "metric": metric, "year": z_obs.index, "z_obs": z_obs.to_numpy(), "z_pred": z_pred.to_numpy()}))

    if not rows:
        sys.exit("Tidak cukup tahun atau stasiun untuk evaluasi. Turunkan --min-years atau perluas data chirps_long.")
    ov, pr = pd.DataFrame(rows), pd.concat(preds, ignore_index=True)
    ov.to_csv(out / "seasonal_overview.csv", index=False)
    pr.to_csv(out / "seasonal_predictions.csv", index=False)
    pd.set_option("display.width", 200)
    print("\n== Skill leave-one-year-out (positif = ENSO/IOD menambah informasi; 1 = sempurna)")
    print(ov.round(2).to_string(index=False))
    print("\n== Tahun sasaran", args.target_year)
    t = pr[pr["year"] == args.target_year]
    print(t.round(2).to_string(index=False) if len(t) else f"tahun {args.target_year} tidak punya data musim lengkap atau prediktor")

    keys = [(r, m) for r in groups for m in ("hth_max", "rain_total") if ((pr.region == r) & (pr.metric == m)).any()]
    if keys:
        fig, axes = plt.subplots(1, len(keys), figsize=(3.8 * len(keys), 3.8), squeeze=False)
        for ax, (r, m) in zip(axes[0], keys):
            d = pr[(pr.region == r) & (pr.metric == m)]
            ax.scatter(d["z_obs"], d["z_pred"], s=14)
            lim = [min(d.z_obs.min(), d.z_pred.min()), max(d.z_obs.max(), d.z_pred.max())]
            ax.plot(lim, lim, "k--", lw=0.8)
            ax.set(title=f"{r}: {m}", xlabel="teramati (z)", ylabel="prediksi LOYO (z)")
        fig.tight_layout()
        fig.savefig(out / "seasonal_scatter.png", dpi=130)
    print("\nTersimpan di", out)


if __name__ == "__main__":
    main()
