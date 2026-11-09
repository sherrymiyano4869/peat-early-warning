"""04_baseline: baseline dan model awal untuk sensor virtual (nowcast) dan prakiraan.

    python scripts/04_baseline.py [--horizons 7 14] [--schemes LOSO LOCO LOIO TEMPORAL] [--quick] [--no-static]

Masuk : data/features/model_table.parquet (hasil 03_assemble)
Keluar: outputs/metrics_overview.csv, metrics_by_cluster.csv, metrics_events.csv, grafik oof_scatter.png

Tugas:
  nowcast  : muka air hari t dari fitur satelit, hujan, dan statis (tanpa muka air)
  forecast : perubahan muka air t -> t+h (delta) dari fitur di t. Varian:
             no_wl       : tanpa muka air (satelit dan hujan saja)
             with_wl     : ditambah muka air t dan tren 3/7 hari (stasiun terpantau)
             oracle_rain : with_wl + hujan MASA DEPAN teramati; DIAGNOSIS batas atas (bukan model sah)
Skema validasi:
  LOSO : satu stasiun ditahan | LOCO : satu klaster ditahan | LOIO : satu pulau ditahan
  TEMPORAL : latih awal periode, uji 25% akhir (stasiun sama). Fitur statis bisa menjadi "KTP stasiun" di skema ini;
             bandingkan dengan --no-static.
Model: baseline (rata-rata / persistensi), Ridge hujan, Ridge AR (muka air dan tren), LightGBM titik dan kuantil q10-q90.
Kejadian: (a) muka air t+h < ambang absolut (config thresholds_cm), (b) pengeringan: delta <= -d cm (config drop_events_cm).
          Kejadian yang hampir selalu atau tak pernah terjadi dilewati.
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
RAIN_COLS = ["rain_7d", "rain_14d", "rain_30d", "dry_days", "dry_max_30d", "rain_days_30d"]
SAT_ABS = ["vv", "vh", "ndmi"]
SAT_ANOM = ["vv_anom", "vh_anom", "ndmi_anom"]
ENSO_COLS = ["nino34", "dmi"]
STATIC_COLS = ["elev_m", "slope_deg", "fabdem_elev_m", "fabdem_slope_deg", "fabdem_relief_500m", "fabdem_relief_1km",
               "canal_density_500m", "canal_density_1km"]
TREND_COLS = ["wl_d3", "wl_d7"]
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
    if scheme in ("LOSO", "LOCO", "LOIO"):
        groups = df[{"LOSO": "station_id", "LOCO": "cluster", "LOIO": "region"}[scheme]].to_numpy()
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
    for variant, cols in variants.items():
        for scheme in schemes:
            splits = make_splits(df, scheme, horizon)
            if not splits:
                continue
            ref_model = MeanModel if ref_name == "mean_train" else ZeroModel
            preds = {ref_name: oof(df, cols["lgb"], y, ref_model, splits),
                     "ridge_rain": oof(df, cols["ridge"], y, make_ridge, splits),
                     "lightgbm": oof(df, cols["lgb"], y, make_lgbm, splits)}
            if cols.get("ar"):
                preds["ridge_ar"] = oof(df, cols["ar"], y, make_ridge, splits)
            if task != "nowcast":
                preds["mean_delta"] = oof(df, cols["lgb"], y, MeanModel, splits)
            ok = ~np.isnan(preds["lightgbm"])
            ref_rmse = rmse(yv[ok], preds[ref_name][ok])
            extra = {}
            if scheme == "LOSO" and not quick:
                q10, q90 = (oof(df, cols["lgb"], y, lambda a=a: make_lgbm(a), splits) for a in (0.1, 0.9))
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


def run_events(df, horizon, events, cols, schemes):
    """events: daftar (nama, y_biner, baseline_tren) ; baseline_tren = tebakan 0/1 dari keadaan terakhir."""
    rows = []
    X = df[cols].to_numpy(float)
    for name, y, trend in events:
        prev = float(y.mean())
        if prev < 0.05 or prev > 0.95:
            rows.append({"horizon": horizon, "event": name, "scheme": "-", "model": "dilewati", "prevalence": round(prev, 3),
                         "note": "kejadian hampir selalu/tidak pernah"})
            continue
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
            for model, p in (("lightgbm", p_lgb), ("keadaan_terakhir", trend), ("prevalence", p_prev)):
                rows.append({"horizon": horizon, "event": name, "scheme": scheme, "model": model, "n": int(ok.sum()),
                             "prevalence": round(float(y[ok].mean()), 3), "brier": brier_score_loss(y[ok], p[ok]),
                             "pr_auc": average_precision_score(y[ok], p[ok]) if y[ok].sum() else np.nan})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--horizons", type=int, nargs="+", default=[7, 14])
    parser.add_argument("--schemes", nargs="+", default=["LOSO", "LOCO", "LOIO", "TEMPORAL"],
                        choices=["LOSO", "LOCO", "LOIO", "TEMPORAL"])
    parser.add_argument("--quick", action="store_true", help="lewati model kuantil")
    parser.add_argument("--no-static", action="store_true", help="buang fitur statis (uji 'KTP stasiun')")
    parser.add_argument("--abs-sat", action="store_true", help="tambahkan VV/VH/NDMI mutlak di samping anomali per stasiun")
    parser.add_argument("--with-enso", action="store_true",
                        help="tambahkan nino34 dan dmi (hampir konstan dalam jendela data; berisiko menjadi penanda tanggal)")
    args = parser.parse_args()

    df = pd.read_parquet(path("features") / "model_table.parquet").sort_values(["station_id", "date"]).reset_index(drop=True)
    rain = [c for c in RAIN_COLS if c in df]
    sat = [c for c in SAT_ANOM if c in df] or [c for c in SAT_ABS if c in df]
    if args.abs_sat:
        sat += [c for c in SAT_ABS if c in df and c not in sat]
    enso = [c for c in ENSO_COLS if c in df] if args.with_enso else []
    if enso:
        distinct = {c: int(df[c].round(2).nunique()) for c in enso}
        print(f"PERINGATAN: ENSO ikut sebagai fitur; nilai berbeda dalam data {distinct}. Dengan nilai sebanyak itu ia bertindak "
              f"sebagai penanda tanggal, bukan bukti pengaruh ENSO.")
    static = [] if args.no_static else [c for c in STATIC_COLS if c in df]
    trend = [c for c in TREND_COLS if c in df]
    dyn = rain + sat + static + enso
    if not dyn:
        sys.exit("Tidak ada fitur di model_table. Jalankan 02_gee_features.py dan 03_assemble.py dulu.")
    print(f"baris {len(df)} | stasiun {df.station_id.nunique()} | klaster {df.cluster.nunique()} | fitur: {dyn}"
          f"{' (tanpa statis)' if args.no_static else ''} | tren: {trend}")
    out = path("outputs")
    cfg = load_config()
    taus, drops = cfg.get("thresholds_cm", [-30, -40, -50]), cfg.get("drop_events_cm", [10, 20])

    overview, by_cluster, events, scatter, scatter_data = [], [], [], {}, {}
    d_now = df.dropna(subset=rain).reset_index(drop=True) if rain else df
    variants = {"no_wl": {"lgb": dyn, "ridge": rain, "ar": None}}
    r, c, k = run_regression(d_now, "nowcast", d_now["wl_cm"], "mean_train", variants, args.schemes, 0, args.quick)
    overview += r; by_cluster += c; scatter.update(k)
    scatter_data["nowcast"] = d_now

    for h in args.horizons:
        fut = df[["station_id", "date", "wl_cm"]].assign(date=lambda x: x["date"] - pd.Timedelta(days=h)).rename(columns={"wl_cm": "wl_future"})
        d = df.merge(fut, on=["station_id", "date"], how="inner")
        d = (d.dropna(subset=rain) if rain else d).reset_index(drop=True)
        d["delta"] = d["wl_future"] - d["wl_cm"]
        if len(d) < 100:
            print(f"h={h}: data terlalu sedikit ({len(d)} baris), dilewati")
            continue
        wl = ["wl_cm"] + trend
        variants = {"no_wl": {"lgb": dyn, "ridge": rain, "ar": None},
                    "with_wl": {"lgb": dyn + wl, "ridge": rain + wl, "ar": wl}}
        oracle = f"fut_rain_{h}d"
        if oracle in d and d[oracle].notna().any():
            variants["oracle_rain"] = {"lgb": dyn + wl + [oracle], "ridge": rain + wl + [oracle], "ar": wl + [oracle]}
        r, c, k = run_regression(d, f"forecast_h{h}", d["delta"], "persistence", variants, args.schemes, h, args.quick)
        overview += r; by_cluster += c; scatter.update(k)
        scatter_data[f"forecast_h{h}"] = d

        ev = [(f"wl<{tau:g}", (d["wl_future"] < tau).astype(int).to_numpy(), (d["wl_cm"] < tau).astype(float).to_numpy()) for tau in taus]
        if "wl_d7" in d:
            ev += [(f"turun>={dd:g}cm", (d["delta"] <= -dd).astype(int).to_numpy(), (d["wl_d7"] <= -dd).astype(float).fillna(0).to_numpy())
                   for dd in drops]
        events += run_events(d, h, ev, dyn + wl, [s for s in args.schemes if s != "LOCO"])

    ov, bc, evd = pd.DataFrame(overview), pd.DataFrame(by_cluster), pd.DataFrame(events)
    ov.to_csv(out / "metrics_overview.csv", index=False)
    bc.to_csv(out / "metrics_by_cluster.csv", index=False)
    evd.to_csv(out / "metrics_events.csv", index=False)

    pd.set_option("display.width", 220)
    print("\n== RMSE (cm) per tugas, varian, skema, dan model")
    print(ov.pivot_table(index=["task", "variant", "scheme"], columns="model", values="rmse").round(2).to_string())
    print("\n== Skill terhadap acuan (persistensi/rata-rata): 1 = sempurna, 0 = sama, < 0 = lebih buruk")
    sk = ov[ov.model.isin(["lightgbm", "ridge_ar"])]
    print(sk.pivot_table(index=["task", "variant", "model"], columns="scheme", values="skill_vs_ref").round(2).to_string())
    if "cover_q10_q90" in ov:
        cov = ov[ov.model == "lightgbm"].dropna(subset=["cover_q10_q90"])
        print("\n== Cakupan interval q10-q90 (target 0.80)")
        print(cov[["task", "variant", "cover_q10_q90", "width_q10_q90"]].round(2).to_string(index=False))
    if len(evd):
        print("\n== Kejadian (Brier lebih kecil lebih baik; PR-AUC lebih besar lebih baik)")
        print(evd.round(3).to_string(index=False))

    keys = [k for k in scatter if k[1] in ("no_wl",) and k[2] == "LOSO"]
    if keys:
        fig, axes = plt.subplots(1, len(keys), figsize=(4.2 * len(keys), 4), squeeze=False)
        for ax, key in zip(axes[0], keys):
            d = scatter_data[key[0]]
            y = d["wl_cm"] if key[0] == "nowcast" else d["delta"]
            p = scatter[key]
            ok = ~np.isnan(p)
            ax.scatter(y[ok], p[ok], s=4, alpha=0.3)
            lim = [min(y[ok].min(), p[ok].min()), max(y[ok].max(), p[ok].max())]
            ax.plot(lim, lim, "k--", lw=0.8)
            ax.set(title=f"{key[0]} (LOSO, LightGBM)", xlabel="teramati (cm)", ylabel="prediksi (cm)")
        fig.tight_layout()
        fig.savefig(out / "oof_scatter.png", dpi=130)
    print("\nTersimpan di", out)


if __name__ == "__main__":
    main()
