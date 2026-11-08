"""04_baseline: baseline dan model awal untuk sensor virtual (nowcast) dan prakiraan.

    python scripts/04_baseline.py [--horizons 7 14] [--schemes LOSO LOCO TEMPORAL] [--quick]

Masuk : data/features/model_table.parquet (hasil 03_assemble)
Keluar: outputs/metrics_overview.csv, metrics_by_cluster.csv, metrics_events.csv, grafik oof_scatter.png

Tugas:
  nowcast  : muka air hari t dari fitur satelit, hujan, dan statis (tanpa muka air)
  forecast : perubahan muka air t -> t+h (delta) dari fitur di t; varian `with_wl` memakai muka air terukur di t
Skema validasi:
  LOSO     : satu stasiun ditahan; LOCO : satu klaster ditahan; TEMPORAL : latih awal periode, uji 25% akhir
Model: baseline (rata-rata latih / persistensi), regresi Ridge (hujan), LightGBM titik, dan kuantil q10-q90.
Kejadian: peluang muka air t+h < ambang (config.yaml: thresholds_cm); ambang yang hampir selalu atau tak pernah terjadi dilewati.
"""
import argparse
import sys
import warnings
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from lightgbm import LGBMClassifier, LGBMRegressor  # noqa: E402
from sklearn.impute import SimpleImputer  # noqa: E402
from sklearn.linear_model import Ridge  # noqa: E402
from sklearn.metrics import average_precision_score, brier_score_loss  # noqa: E402
from sklearn.model_selection import LeaveOneGroupOut  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import load_config, path  # noqa: E402

warnings.filterwarnings("ignore", category=UserWarning)
RAIN_COLS = ["rain_7d", "rain_14d", "rain_30d", "dry_days"]
SAT_COLS = ["vv", "vh", "ndmi"]
STATIC_COLS = ["elev_m", "slope_deg"]
LGB = dict(n_estimators=200, learning_rate=0.05, num_leaves=15, min_child_samples=30, subsample=0.8,
           subsample_freq=1, colsample_bytree=0.8, random_state=0, verbose=-1, n_jobs=1)


class MeanModel:
    def fit(self, X, y):
        self.m_ = float(np.nanmean(y))
        return self

    def predict(self, X):
        return np.full(len(X), self.m_)


class ZeroModel:
    def fit(self, X, y):
        return self

    def predict(self, X):
        return np.zeros(len(X))


def make_ridge():
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=10.0))


def make_lgbm(alpha=None):
    return LGBMRegressor(objective="quantile", alpha=alpha, **LGB) if alpha else LGBMRegressor(**LGB)


def make_splits(df: pd.DataFrame, scheme: str, horizon: int) -> list:
    if scheme in ("LOSO", "LOCO"):
        groups = df["station_id" if scheme == "LOSO" else "cluster"].to_numpy()
        return list(LeaveOneGroupOut().split(df, groups=groups)) if len(np.unique(groups)) > 1 else []
    dates = np.sort(df["date"].unique())
    cutoff = pd.Timestamp(dates[int(len(dates) * 0.75)])
    train = np.where(df["date"] <= cutoff - pd.Timedelta(days=horizon))[0]  # jarak h hari agar target latih tak menyentuh uji
    test = np.where(df["date"] > cutoff)[0]
    return [(train, test)] if len(train) and len(test) else []


def oof(df, cols, y, make_model, splits):
    X, yv, pred = df[cols].to_numpy(float), y.to_numpy(float), np.full(len(df), np.nan)
    for tr, te in splits:
        pred[te] = make_model().fit(X[tr], yv[tr]).predict(X[te])
    return pred


def rmse(y, p):
    ok = ~np.isnan(p)
    return float(np.sqrt(np.mean((y[ok] - p[ok]) ** 2))) if ok.any() else np.nan


def mae(y, p):
    ok = ~np.isnan(p)
    return float(np.mean(np.abs(y[ok] - p[ok]))) if ok.any() else np.nan


def run_regression(df, task, y, ref_name, variants, schemes, horizon, quick):
    rows, cluster_rows, keep = [], [], {}
    yv = y.to_numpy(float)
    for variant, (lgb_cols, ridge_cols) in variants.items():
        for scheme in schemes:
            splits = make_splits(df, scheme, horizon)
            if not splits:
                continue
            preds = {ref_name: oof(df, lgb_cols, y, MeanModel if ref_name == "mean_train" else ZeroModel, splits),
                     "ridge_rain": oof(df, ridge_cols, y, make_ridge, splits),
                     "lightgbm": oof(df, lgb_cols, y, make_lgbm, splits)}
            if task != "nowcast":
                preds["mean_delta"] = oof(df, lgb_cols, y, MeanModel, splits)
            ok = ~np.isnan(preds["lightgbm"])
            ref_rmse = rmse(yv[ok], preds[ref_name][ok])
            extra = {}
            if scheme == "LOSO" and not quick:
                q10, q90 = (oof(df, lgb_cols, y, lambda a=a: make_lgbm(a), splits) for a in (0.1, 0.9))
                inside = (yv >= q10) & (yv <= q90)
                extra = {"cover_q10_q90": float(np.mean(inside[ok])), "width_q10_q90": float(np.nanmean((q90 - q10)[ok]))}
            for name, p in preds.items():
                r = rmse(yv[ok], p[ok])
                rows.append({"task": task, "variant": variant, "scheme": scheme, "model": name, "n": int(ok.sum()),
                             "rmse": r, "mae": mae(yv[ok], p[ok]), "skill_vs_ref": 1 - r / ref_rmse if ref_rmse else np.nan,
                             **(extra if name == "lightgbm" else {})})
            keep[(task, variant, scheme)] = preds["lightgbm"]
            if scheme == "LOSO":
                for cl, g in df[ok].groupby("cluster"):
                    idx = g.index.to_numpy()
                    cr, rr = rmse(yv[idx], preds["lightgbm"][idx]), rmse(yv[idx], preds[ref_name][idx])
                    cluster_rows.append({"task": task, "variant": variant, "cluster": cl, "n_stasiun": g["station_id"].nunique(),
                                         "n": len(g), "rmse_lightgbm": cr, "rmse_ref": rr, "skill": 1 - cr / rr if rr else np.nan})
    return rows, cluster_rows, keep


def run_events(df, horizon, taus, cols, schemes):
    rows = []
    for tau in taus:
        y = (df["wl_future"] < tau).astype(int).to_numpy()
        prev = y.mean()
        if prev < 0.05 or prev > 0.95:
            rows.append({"horizon": horizon, "tau_cm": tau, "scheme": "-", "model": "dilewati",
                         "prevalence": round(float(prev), 3), "note": "kejadian hampir selalu/tidak pernah"})
            continue
        X = df[cols].to_numpy(float)
        persistence = (df["wl_cm"] < tau).astype(float).to_numpy()
        for scheme in schemes:
            splits = make_splits(df, scheme, horizon)
            if not splits:
                continue
            p_lgb, p_prev = np.full(len(df), np.nan), np.full(len(df), np.nan)
            for tr, te in splits:
                if y[tr].min() == y[tr].max():
                    p_lgb[te] = float(y[tr][0])
                else:
                    p_lgb[te] = LGBMClassifier(**LGB).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
                p_prev[te] = y[tr].mean()
            ok = ~np.isnan(p_lgb)
            for name, p in (("lightgbm", p_lgb), ("persistence", persistence), ("prevalence", p_prev)):
                rows.append({"horizon": horizon, "tau_cm": tau, "scheme": scheme, "model": name, "n": int(ok.sum()),
                             "prevalence": round(float(y[ok].mean()), 3), "brier": brier_score_loss(y[ok], p[ok]),
                             "pr_auc": average_precision_score(y[ok], p[ok]) if y[ok].sum() else np.nan})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--horizons", type=int, nargs="+", default=[7, 14])
    parser.add_argument("--schemes", nargs="+", default=["LOSO", "LOCO", "TEMPORAL"], choices=["LOSO", "LOCO", "TEMPORAL"])
    parser.add_argument("--quick", action="store_true", help="lewati model kuantil")
    args = parser.parse_args()

    df = pd.read_parquet(path("features") / "model_table.parquet").sort_values(["station_id", "date"]).reset_index(drop=True)
    rain = [c for c in RAIN_COLS if c in df]
    sat = [c for c in SAT_COLS if c in df]
    static = [c for c in STATIC_COLS if c in df]
    dyn = rain + sat + static
    if not dyn:
        sys.exit("Tidak ada fitur di model_table. Jalankan 02_gee_features.py dan 03_assemble.py dulu.")
    print(f"baris {len(df)} | stasiun {df.station_id.nunique()} | klaster {df.cluster.nunique()} | fitur: {dyn}")
    out = path("outputs")
    taus = load_config().get("thresholds_cm", [-30, -40, -50])

    overview, by_cluster, events, scatter = [], [], [], {}
    d_now = df.dropna(subset=rain).reset_index(drop=True) if rain else df
    r, c, k = run_regression(d_now, "nowcast", d_now["wl_cm"], "mean_train", {"no_wl": (dyn, rain)}, args.schemes, 0, args.quick)
    overview += r; by_cluster += c; scatter.update(k)
    scatter_data = {"nowcast": d_now}

    for h in args.horizons:
        fut = df[["station_id", "date", "wl_cm"]].assign(date=lambda x: x["date"] - pd.Timedelta(days=h)).rename(columns={"wl_cm": "wl_future"})
        d = df.merge(fut, on=["station_id", "date"], how="inner")
        d = (d.dropna(subset=rain) if rain else d).reset_index(drop=True)
        d["delta"] = d["wl_future"] - d["wl_cm"]
        if len(d) < 100:
            print(f"h={h}: data terlalu sedikit ({len(d)} baris), dilewati")
            continue
        variants = {"no_wl": (dyn, rain), "with_wl": (dyn + ["wl_cm"], rain + ["wl_cm"])}
        r, c, k = run_regression(d, f"forecast_h{h}", d["delta"], "persistence", variants, args.schemes, h, args.quick)
        overview += r; by_cluster += c; scatter.update(k)
        scatter_data[f"forecast_h{h}"] = d
        events += run_events(d, h, taus, dyn + ["wl_cm"], [s for s in args.schemes if s != "LOCO"])

    ov, bc, ev = pd.DataFrame(overview), pd.DataFrame(by_cluster), pd.DataFrame(events)
    ov.to_csv(out / "metrics_overview.csv", index=False)
    bc.to_csv(out / "metrics_by_cluster.csv", index=False)
    ev.to_csv(out / "metrics_events.csv", index=False)

    pd.set_option("display.width", 200)
    print("\n== RMSE (cm) per tugas, varian, skema, dan model")
    print(ov.pivot_table(index=["task", "variant", "scheme"], columns="model", values="rmse").round(2).to_string())
    print("\n== Skill LightGBM terhadap baseline acuan (1 = sempurna, 0 = sama, < 0 = lebih buruk)")
    print(ov[ov.model == "lightgbm"].pivot_table(index=["task", "variant"], columns="scheme", values="skill_vs_ref").round(2).to_string())
    if "cover_q10_q90" in ov:
        cov = ov[ov.model == "lightgbm"].dropna(subset=["cover_q10_q90"])
        print("\n== Cakupan interval q10-q90 (target 0.80)")
        print(cov[["task", "variant", "cover_q10_q90", "width_q10_q90"]].round(2).to_string(index=False))
    if len(ev):
        print("\n== Kejadian (Brier lebih kecil lebih baik; PR-AUC lebih besar lebih baik)")
        print(ev.round(3).to_string(index=False))

    keys = [k for k in scatter if k[1] in ("no_wl",) and k[2] == "LOSO"]
    if keys:
        fig, axes = plt.subplots(1, len(keys), figsize=(4.2 * len(keys), 4), squeeze=False)
        for ax, key in zip(axes[0], keys):
            task, _, _ = key
            d = scatter_data[task]
            y = d["wl_cm"] if task == "nowcast" else d["delta"]
            p = scatter[key]
            ok = ~np.isnan(p)
            ax.scatter(y[ok], p[ok], s=4, alpha=0.3)
            lim = [min(y[ok].min(), p[ok].min()), max(y[ok].max(), p[ok].max())]
            ax.plot(lim, lim, "k--", lw=0.8)
            ax.set(title=f"{task} (LOSO, LightGBM)", xlabel="teramati (cm)", ylabel="prediksi (cm)")
        fig.tight_layout()
        fig.savefig(out / "oof_scatter.png", dpi=130)
    print("\nTersimpan di", out)


if __name__ == "__main__":
    main()
