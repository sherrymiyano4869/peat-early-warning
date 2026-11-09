"""06_predict: prediksi ke depan per stasiun (prototipe) dan uji walk-forward mingguan.

    python scripts/06_predict.py                      # tanggal terbit = tanggal terbaru yang fiturnya lengkap
    python scripts/06_predict.py --issue-date 2026-10-20
    python scripts/06_predict.py --walk-forward       # simulasi operasional: terbitkan tiap minggu, nilai setelah kenyataan ada

Masuk : data/features/model_table.parquet (hasil 03_assemble)
Keluar: outputs/predictions_latest.csv, atau outputs/walkforward_predictions.csv dan walkforward_summary.csv

Prediksi: perubahan muka air `delta` (cm) dalam h hari (median dan rentang q10-q90) dan peluang pengeringan (turun >= d cm),
memakai fitur di tanggal terbit: hujan, anomali satelit, statis (DEM, kanal), muka air terukur dan tren 3/7 hari.
Tanpa kebocoran: latihan hanya memakai baris yang targetnya (tanggal + h) sudah terjadi pada atau sebelum tanggal terbit.
Pembanding: persistensi (delta = 0) dan frekuensi kejadian di data latih.
STATUS: prototipe; peluang belum dikalibrasi, dan skill melampaui persistensi belum terbukti sampai walk-forward menunjukkannya.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import load_config, path  # noqa: E402
from src.modeling import LGB, make_lgbm, feature_sets  # noqa: E402


def pairs(df: pd.DataFrame, h: int) -> pd.DataFrame:
    fut = df[["station_id", "date", "wl_cm"]].assign(date=lambda x: x["date"] - pd.Timedelta(days=h)).rename(columns={"wl_cm": "wl_future"})
    d = df.merge(fut, on=["station_id", "date"], how="left")
    d["delta"] = d["wl_future"] - d["wl_cm"]
    return d


def default_issue_date(df: pd.DataFrame, rain_cols: list) -> pd.Timestamp:
    ok = df.dropna(subset=["wl_cm"] + rain_cols[:1]).groupby("date")["station_id"].nunique()
    total = df["station_id"].nunique()
    return ok[ok >= 0.5 * total].index.max()


def predict_issue(d: pd.DataFrame, issue: pd.Timestamp, h: int, cols: list, rain_cols: list, drops: list, min_rows: int):
    """Latih dengan data yang sudah diketahui pada tanggal terbit, lalu prediksi untuk stasiun pada tanggal itu."""
    train = d[(d["date"] <= issue - pd.Timedelta(days=h)) & d["delta"].notna()].dropna(subset=rain_cols[:1])
    now = d[(d["date"] == issue)].dropna(subset=["wl_cm"] + rain_cols[:1])
    if len(train) < min_rows or now.empty:
        return None
    assert (train["date"] + pd.Timedelta(days=h)).max() <= issue, "kebocoran: target latih melewati tanggal terbit"
    X, y, Xn = train[cols].to_numpy(float), train["delta"].to_numpy(float), now[cols].to_numpy(float)
    out = pd.DataFrame({"station_id": now["station_id"].to_numpy(), "issue_date": issue, "horizon": h,
                        "wl_now_cm": now["wl_cm"].to_numpy(), "n_train": len(train)})
    out["delta_med"] = make_lgbm().fit(X, y).predict(Xn)
    out["delta_q10"] = make_lgbm(0.1).fit(X, y).predict(Xn)
    out["delta_q90"] = make_lgbm(0.9).fit(X, y).predict(Xn)
    out["wl_pred_cm"] = out["wl_now_cm"] + out["delta_med"]
    for dd in drops:
        yb = (y <= -dd).astype(int)
        out[f"p_turun{dd:g}"] = float(yb[0]) if yb.min() == yb.max() else LGBMClassifier(**LGB).fit(X, yb).predict_proba(Xn)[:, 1]
        out[f"p_turun{dd:g}_basis"] = float(yb.mean())  # frekuensi kejadian di data latih
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--horizons", type=int, nargs="+", default=[7, 14])
    parser.add_argument("--issue-date")
    parser.add_argument("--walk-forward", action="store_true")
    parser.add_argument("--wf-step", type=int, default=7, help="selang hari antar tanggal terbit pada walk-forward")
    parser.add_argument("--min-train-rows", type=int, default=400)
    parser.add_argument("--no-static", action="store_true")
    parser.add_argument("--abs-sat", action="store_true")
    args = parser.parse_args()

    df = pd.read_parquet(path("features") / "model_table.parquet").sort_values(["station_id", "date"]).reset_index(drop=True)
    rain, sat, static, trend, _ = feature_sets(df, args.no_static, args.abs_sat)
    cols = rain + sat + static + ["wl_cm"] + trend
    drops = load_config().get("drop_events_cm", [10, 20])
    out_dir = path("outputs")
    last = df["date"].max()
    print(f"data sampai {last.date()} | stasiun {df.station_id.nunique()} | fitur {len(cols)}: {cols}")

    if not args.walk_forward:
        issue = pd.Timestamp(args.issue_date) if args.issue_date else default_issue_date(df, rain)
        print(f"tanggal terbit: {issue.date()}")
        frames = []
        for h in args.horizons:
            res = predict_issue(pairs(df, h), issue, h, cols, rain, drops, args.min_train_rows)
            if res is None:
                print(f"h={h}: data latih kurang (< {args.min_train_rows} baris) atau tak ada stasiun berfitur lengkap pada {issue.date()}")
                continue
            frames.append(res)
        if not frames:
            sys.exit("Tidak ada prediksi yang bisa dibuat. Turunkan --min-train-rows atau pilih --issue-date lain.")
        pred = pd.concat(frames, ignore_index=True)
        pred.to_csv(out_dir / "predictions_latest.csv", index=False)
        pd.set_option("display.width", 200)
        for h, g in pred.groupby("horizon"):
            key = f"p_turun{drops[0]:g}"
            print(f"\n== Horizon {h} hari (urut menurut {key}); {len(g)} stasiun, {int(g.n_train.iloc[0])} baris latih")
            print(g.sort_values(key, ascending=False)[["station_id", "wl_now_cm", "delta_q10", "delta_med", "delta_q90", key, f"{key}_basis"]]
                  .head(12).round(2).to_string(index=False))
        print("\nTersimpan: outputs/predictions_latest.csv  (prototipe; peluang belum dikalibrasi)")
        return

    # walk-forward: terbitkan tiap `wf_step` hari; nilai setelah kenyataan t+h tersedia
    rows = []
    all_dates = sorted(df["date"].unique())
    for h in args.horizons:
        d = pairs(df, h)
        for issue in all_dates:
            issue = pd.Timestamp(issue)
            if (issue - all_dates[0]).days % args.wf_step != 0 or issue + pd.Timedelta(days=h) > last:
                continue
            res = predict_issue(d, issue, h, cols, rain, drops, args.min_train_rows)
            if res is None:
                continue
            actual = d[d["date"] == issue][["station_id", "delta", "wl_d7"]]
            rows.append(res.merge(actual, on="station_id", how="inner").dropna(subset=["delta"]))
    if not rows:
        sys.exit("Tidak ada tanggal terbit yang memenuhi syarat. Turunkan --min-train-rows atau --wf-step.")
    wf = pd.concat(rows, ignore_index=True)
    wf.to_csv(out_dir / "walkforward_predictions.csv", index=False)

    summary = []
    for h, g in wf.groupby("horizon"):
        rm, rp = np.sqrt(np.mean((g.delta - g.delta_med) ** 2)), np.sqrt(np.mean(g.delta ** 2))
        row = {"horizon": h, "n": len(g), "tanggal_terbit": g.issue_date.nunique(), "rmse_model": rm, "rmse_persistensi": rp,
               "skill_vs_persistensi": 1 - rm / rp, "cakupan_q10_q90": float(((g.delta >= g.delta_q10) & (g.delta <= g.delta_q90)).mean())}
        for dd in drops:
            yb = (g.delta <= -dd).astype(int)
            row[f"brier_turun{dd:g}_model"] = float(np.mean((g[f"p_turun{dd:g}"] - yb) ** 2))
            row[f"brier_turun{dd:g}_basis"] = float(np.mean((g[f"p_turun{dd:g}_basis"] - yb) ** 2))
            row[f"brier_turun{dd:g}_tren"] = float(np.mean(((g.wl_d7 <= -dd).astype(float).fillna(0) - yb) ** 2))
            row[f"frekuensi_turun{dd:g}"] = float(yb.mean())
        summary.append(row)
    sm = pd.DataFrame(summary)
    sm.to_csv(out_dir / "walkforward_summary.csv", index=False)
    pd.set_option("display.width", 220)
    print("\n== Walk-forward (tiap tanggal terbit hanya memakai data yang sudah diketahui saat itu)")
    print(sm.round(3).T.to_string(header=False))
    print("\nBaca: skill > 0 berarti lebih baik daripada persistensi; Brier model < basis dan < tren berarti peluangnya berguna.")
    print("Tersimpan: outputs/walkforward_predictions.csv dan walkforward_summary.csv")


if __name__ == "__main__":
    main()
