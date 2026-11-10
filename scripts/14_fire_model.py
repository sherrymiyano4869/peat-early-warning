"""14_fire_model: peluang ada titik api VIIRS di sel 1 km dalam 1 dan 3 hari ke depan (LightGBM), dengan pembanding dan gerbang bukti.

    python scripts/14_fire_model.py [--test-days 365 --calib-days 180] [--dynamic data/features/dynamic_daily.parquet]

Masuk : data/features/fire_cell_day.parquet (13), data/features/grid/{static,risk_class}.tif dan grid_meta.json (07, 08)
        opsional --dynamic berkas...: fitur dinamis (hujan, hari tanpa hujan, kelembapan tanah, NDMI, ENSO/DMI) dalam empat format
        (sel-hari, piksel-hari, regional, sel-jendela; lihat src/cells.py). HANYA nilai yang sudah diketahui pada tanggal itu
Keluar: outputs/fire_metrics.json              metrik uji, pembanding, kurva keandalan, dan gerbang (skill_ok, kelas kepercayaan)
        outputs/fire_prob_latest.parquet       peluang p1 dan p3 per sel untuk tanggal terbit terakhir (+ klimatologi)
        outputs/fire_top_cells.geojson         sel teratas (bawaan 5 persen) untuk web
        outputs/models/fire_<tanggal>.txt/.json model dan metadata

Definisi: pada hari t (setelah data hari t diketahui), y1 = ada >= 1 deteksi VIIRS di sel pada hari t+1; y3 = ada >= 1 pada t+1..t+3.
Ini PELUANG per sel, bukan titik pasti: api gambut umumnya dipicu manusia, label VIIRS jarang dan bias awan dan asap.
Fitur hanya dari data <= t (diuji penyebab-akibat tiap run). Pembagian waktu: latih | (jeda h hari) | kalibrasi | (jeda) | uji; kalibrasi isotonik pada
segmen kalibrasi. Pembanding: klimatologi sel-bulan (dari data latih) dan persistensi (deteksi baru di sel atau tetangga). Metrik dilaporkan untuk
bulan musim api (Jun-Nov) karena bulan lain hampir semua negatif.
Gerbang: skill_ok hanya bila model mengalahkan KEDUA pembanding pada PR-AUC, punya skill Brier > 0 terhadap klimatologi, dan Brier lebih kecil
daripada persistensi di data uji.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import rasterio
from scipy import ndimage
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import path  # noqa: E402
from src.cells import counts_cube, load_dynamic_cubes, load_universe  # noqa: E402
from src.grid import cell_id, cell_polygon_lonlat, cell_center_lonlat  # noqa: E402

SEASON = (6, 7, 8, 9, 10, 11)
WARMUP = 30
PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=31, min_data_in_leaf=200, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
              lambda_l2=1.0, verbose=-1, seed=7, deterministic=True, force_row_wise=True)


# ------------------------------------------------------------------ data (pemuat bersama: src/cells.py)


def roll_sum(cube: np.ndarray, w: int) -> np.ndarray:
    cs = np.cumsum(cube.astype(np.int32), axis=0)
    out = cs.copy()
    out[w:] -= cs[:-w]
    return out


def build_features(cube: np.ndarray, dates: pd.DatetimeIndex, uni: dict, dynamic: dict | None = None) -> dict:
    """Fitur pada hari t memakai HANYA cube[:t+1]."""
    T = len(dates)
    feats = {}
    feats["n_d0"] = cube.astype("float32")
    for w in (3, 7, 30, 90):
        feats[f"n_{w}d"] = roll_sum(cube, w).astype("float32")
    for w in (7, 30):
        nb = ndimage.uniform_filter(roll_sum(cube, w).astype("float32"), size=(1, 3, 3), mode="constant") * 9.0
        feats[f"nb_{w}d"] = nb
    idx = np.where(cube > 0, np.arange(T)[:, None, None], -1)
    last = np.maximum.accumulate(idx, axis=0)
    feats["days_since"] = np.minimum(np.where(last >= 0, np.arange(T)[:, None, None] - last, 365), 365).astype("float32")
    doy = dates.dayofyear.to_numpy()
    ang = 2 * np.pi * doy / 365.25
    for name, v in (("doy_sin", np.sin(ang)), ("doy_cos", np.cos(ang))):
        feats[name] = np.broadcast_to(v.astype("float32")[:, None, None], cube.shape)
    for k, a in uni["static"].items():
        feats[k] = np.broadcast_to(a[None], cube.shape)
    for k, a in (dynamic or {}).items():
        feats[k] = a
    return feats


def make_labels(cube: np.ndarray, h: int) -> np.ndarray:
    """y_h[t] = ada deteksi pada t+1..t+h; tak terdefinisi (-1) pada h hari terakhir."""
    T = cube.shape[0]
    y = np.full(cube.shape, -1, dtype="int8")
    fut = np.zeros(cube.shape, dtype=np.int32)
    for k in range(1, h + 1):
        fut[: T - k] += cube[k:]
    y[: T - h] = (fut[: T - h] > 0).astype("int8")
    return y


def check_causality(cube, dates, uni, feats, rng, n_dates=3):
    """Hitung ulang fitur dari data yang dipotong sampai t dan bandingkan dengan fitur penuh pada t."""
    T = len(dates)
    for t in rng.choice(np.arange(WARMUP, T), size=n_dates, replace=False):
        part = build_features(cube[: t + 1], dates[: t + 1], uni)
        for name, arr in part.items():
            if name.startswith(("canal", "fabdem")):
                continue
            if not np.allclose(arr[t], feats[name][t], atol=1e-5, equal_nan=True):
                raise AssertionError(f"Kebocoran: fitur {name} pada t={dates[t].date()} berubah bila data masa depan dibuang")
    return True


# ------------------------------------------------------------------ evaluasi
def topk_capture(P: np.ndarray, Y: np.ndarray, frac: float) -> float:
    k = max(1, int(round(P.shape[1] * frac)))
    cap, tot = 0, 0
    for p, y in zip(P, Y):
        pos = int(y.sum())
        if pos == 0:
            continue
        top = np.argpartition(-p, k - 1)[:k]
        cap += int(y[top].sum()); tot += pos
    return cap / tot if tot else float("nan")


def reliability(p: np.ndarray, y: np.ndarray):
    edges = [0, 0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0001]
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p < hi)
        if m.sum() >= 50:
            out.append({"p_awal": lo, "p_akhir": min(hi, 1.0), "n": int(m.sum()), "p_rata2": round(float(p[m].mean()), 5), "frekuensi_nyata": round(float(y[m].mean()), 5)})
    return out


def evaluate(P2d, Y2d, clim2d, persist2d, season_mask):
    """P2d dan lainnya: (hari, sel). Hanya hari musim api (season_mask) yang dinilai."""
    P, Y, C, R = (a[season_mask] for a in (P2d, Y2d, clim2d, persist2d))
    p, y, c, r = P.ravel(), Y.ravel(), C.ravel(), R.ravel()
    brier = lambda q: float(np.mean((q - y) ** 2))
    out = {"n_cell_hari": int(y.size), "n_positif": int(y.sum()), "laju_positif": round(float(y.mean()), 5)}
    if y.sum() == 0 or y.sum() == y.size:
        return out | {"catatan": "tidak ada positif pada data uji"}
    for name, q in (("model", p), ("klimatologi", c), ("persistensi", r)):
        out[name] = {"pr_auc": round(float(average_precision_score(y, q)), 4), "roc_auc": round(float(roc_auc_score(y, q)), 4), "brier": round(brier(q), 6),
                     "tangkapan_5persen": round(topk_capture(P if name == "model" else (C if name == "klimatologi" else R), Y, 0.05), 4)}
    out["skill_brier_vs_klimatologi"] = round(1 - brier(p) / brier(c), 4)
    out["keandalan"] = reliability(p, y)
    return out


def split_dates(T, dates, test_days, calib_days, h):
    test_start = T - test_days
    calib_start = test_start - calib_days
    train_idx = np.arange(WARMUP, calib_start - h)
    calib_idx = np.arange(calib_start, test_start - h)
    test_idx = np.arange(test_start, T - h)
    return train_idx, calib_idx, test_idx


def flat(feats, names, idx, valid):
    X = np.stack([np.asarray(feats[n])[idx][:, valid] for n in names], axis=-1)    # (hari, sel, fitur)
    return X.reshape(-1, len(names)).astype("float32")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--test-days", type=int, default=365); ap.add_argument("--calib-days", type=int, default=180)
    ap.add_argument("--horizons", type=int, nargs="+", default=[1, 3])
    ap.add_argument("--dynamic", nargs="+", help="satu atau lebih berkas fitur dinamis (format: lihat src/cells.py)"); ap.add_argument("--max-train-rows", type=int, default=6_000_000)
    ap.add_argument("--top-frac", type=float, default=0.05)
    args = ap.parse_args()
    rng = np.random.default_rng(7)

    grid_dir = path("features") / "grid"
    need = [path("features") / "fire_cell_day.parquet", grid_dir / "static.tif", grid_dir / "grid_meta.json"]
    for f in need:
        if not f.exists():
            sys.exit(f"{f} tidak ada. Jalankan 13_hotspots_to_cells.py dan 07_grid_static.py dulu.")
    uni = load_universe(grid_dir)
    cell_day = pd.read_parquet(need[0])
    cell_day["date"] = pd.to_datetime(cell_day["date"])
    dates = pd.date_range(cell_day["date"].min(), cell_day["date"].max(), freq="D")
    cube, dropped = counts_cube(cell_day, dates, uni)
    hh, ww = uni["shape"]; valid = uni["valid"]
    print(f"kubus: {len(dates)} hari x {hh} x {ww} sel 1 km | sel bernilai {int(valid.sum()):,} | sel-hari api di luar grid dibuang: {dropped}")
    if len(dates) < args.test_days + args.calib_days + 400:
        sys.exit("Data terlalu pendek untuk pembagian latih/kalibrasi/uji; kurangi --test-days/--calib-days atau tambah tahun data.")

    dyn = None
    if args.dynamic:
        dyn = load_dynamic_cubes(args.dynamic, dates, uni)
        print("fitur dinamis:", {k: f"{float(np.isfinite(v).mean()):.0%} terisi" for k, v in dyn.items()})
    feats = build_features(cube, dates, uni, dyn)
    names = list(feats)
    check_causality(cube, dates, uni, {k: v for k, v in feats.items() if k not in (dyn or {})}, rng)
    print("uji penyebab-akibat (fitur hanya dari data <= t): LOLOS | fitur:", [n for n in names])

    metrics = {"dibuat": datetime.now(timezone.utc).isoformat(timespec="seconds"), "tanggal_data_terakhir": str(dates[-1].date()), "fitur": names, "horizon": {}}
    models, calibrators, climatology_cache = {}, {}, {}
    month = dates.month.to_numpy()
    for h in args.horizons:
        y = make_labels(cube, h)
        tr, ca, te = split_dates(len(dates), dates, args.test_days, args.calib_days, h)
        nv = int(valid.sum())
        Xtr, ytr = flat(feats, names, tr, valid), y[tr][:, valid].ravel()
        Xca, yca = flat(feats, names, ca, valid), y[ca][:, valid].ravel()
        Xte, yte2d = flat(feats, names, te, valid), y[te][:, valid]
        w = np.ones(len(ytr), dtype="float32")
        if len(ytr) > args.max_train_rows:   # kurangi negatif saja; bobot menjaga rasio
            neg = np.nonzero(ytr == 0)[0]; keep_neg = rng.choice(neg, size=args.max_train_rows - int((ytr == 1).sum()), replace=False)
            sel = np.sort(np.concatenate([np.nonzero(ytr == 1)[0], keep_neg])); w_full = np.ones(len(ytr), dtype="float32"); w_full[neg] = len(neg) / len(keep_neg)
            Xtr, ytr, w = Xtr[sel], ytr[sel], w_full[sel]
        d_tr, d_ca = lgb.Dataset(Xtr, ytr, weight=w, feature_name=names), lgb.Dataset(Xca, yca, feature_name=names)
        booster = lgb.train(PARAMS, d_tr, num_boost_round=800, valid_sets=[d_ca], callbacks=[lgb.early_stopping(60, verbose=False)])
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(booster.predict(Xca, num_iteration=booster.best_iteration), yca)
        p_te = iso.predict(booster.predict(Xte, num_iteration=booster.best_iteration)).reshape(len(te), nv)

        # pembanding dari semua label yang sudah diketahui sebelum hari uji pertama (label hari t baru diketahui setelah t+h)
        known = te[0] - h
        yf = y[:known][:, valid]; mm = month[:known]
        clim_cm = np.zeros((12, nv)); glob_m = np.zeros(12)
        for m in range(1, 13):
            sel = (mm == m) & (np.arange(len(mm)) >= WARMUP)
            if sel.sum():
                glob_m[m - 1] = yf[sel].mean(); clim_cm[m - 1] = (yf[sel].sum(0) + 20 * glob_m[m - 1]) / (sel.sum() + 20)
            else:
                clim_cm[m - 1] = 0.0
        clim_te = clim_cm[month[te] - 1]
        score_te = np.asarray(feats["n_7d"])[te][:, valid] + 0.3 * np.asarray(feats["nb_7d"])[te][:, valid]
        score_ca = np.asarray(feats["n_7d"])[ca][:, valid] + 0.3 * np.asarray(feats["nb_7d"])[ca][:, valid]
        iso_r = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(score_ca.ravel(), yca)
        pers_te = iso_r.predict(score_te.ravel()).reshape(score_te.shape)
        season = np.isin(month[te], SEASON)
        ev = evaluate(p_te, yte2d, clim_te, pers_te, season)
        imp = dict(zip(names, booster.feature_importance("gain").round(1).tolist()))
        ev["importance_gain"] = dict(sorted(imp.items(), key=lambda kv: -kv[1])[:8])
        ev["jumlah_pohon"] = int(booster.best_iteration or booster.current_iteration())
        ev["periode"] = {"latih": [str(dates[tr[0]].date()), str(dates[tr[-1]].date())], "kalibrasi": [str(dates[ca[0]].date()), str(dates[ca[-1]].date())],
                         "uji": [str(dates[te[0]].date()), str(dates[te[-1]].date())]}
        if "model" in ev:
            m_, c_, r_ = ev["model"], ev["klimatologi"], ev["persistensi"]
            ev["skill_ok"] = bool(m_["pr_auc"] > max(c_["pr_auc"], r_["pr_auc"]) and ev["skill_brier_vs_klimatologi"] > 0 and m_["brier"] < r_["brier"])
        else:
            ev["skill_ok"] = False
        metrics["horizon"][f"h{h}"] = ev
        models[h], calibrators[h] = booster, iso
        climatology_cache[h] = clim_cm
        print(f"\nhorizon {h} hari | uji {ev['periode']['uji'][0]}..{ev['periode']['uji'][1]} (musim Jun-Nov): positif {ev.get('n_positif', 0)} dari {ev['n_cell_hari']:,} sel-hari")
        for k in ("model", "klimatologi", "persistensi"):
            if k in ev:
                print(f"  {k:12s} PR-AUC {ev[k]['pr_auc']:.3f} | ROC-AUC {ev[k]['roc_auc']:.3f} | Brier {ev[k]['brier']:.5f} | tangkapan 5% sel {ev[k]['tangkapan_5persen']:.0%}")
        print(f"  skill Brier vs klimatologi {ev.get('skill_brier_vs_klimatologi', float('nan')):+.3f} | skill_ok = {ev['skill_ok']}")
    all_ok = all(v["skill_ok"] for v in metrics["horizon"].values())
    metrics["skill_ok"] = all_ok
    metrics["cap_class"] = 1 if all_ok else 0     # tinggi (2) hanya setelah lolos penilaian prospektif berulang pada arsip
    metrics["catatan"] = "Uji retrospektif pada satu periode; belum menggantikan penilaian prospektif atas arsip prediksi."

    # ---- prediksi tanggal terbit terakhir
    T = len(dates) - 1
    Xnow = np.stack([np.asarray(feats[n])[T][valid] for n in names], axis=-1).astype("float32")
    rr, cc = np.nonzero(valid)
    cx, cy = uni["cx0"] + cc, uni["cy_top"] - rr
    out = pd.DataFrame({"cell_id": cell_id(cx, cy), "cx": cx, "cy": cy})
    for h in args.horizons:
        out[f"p{h}"] = calibrators[h].predict(models[h].predict(Xnow, num_iteration=models[h].best_iteration))
        out[f"p{h}_klim"] = climatology_cache[h][dates[T].month - 1]
    out["lon"], out["lat"] = cell_center_lonlat(cx, cy)
    out["issue_date"] = str(dates[T].date())
    first = f"p{args.horizons[0]}"
    out["rank"] = out[first].rank(ascending=False, method="first").astype(int)
    outputs = path("outputs"); (outputs / "models").mkdir(parents=True, exist_ok=True)
    out.to_parquet(outputs / "fire_prob_latest.parquet", index=False)
    top = out[out["rank"] <= max(1, int(round(len(out) * args.top_frac)))].sort_values("rank")
    feats_geo = [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [cell_polygon_lonlat(int(r.cx), int(r.cy))]},
                  "properties": {"rank": int(r.rank), **{k: round(float(getattr(r, k)), 4) for k in out.columns if k.startswith("p")}}} for r in top.itertuples()]
    (outputs / "fire_top_cells.geojson").write_text(json.dumps({"type": "FeatureCollection", "issue_date": str(dates[T].date()), "horizons": args.horizons,
                                                                "top_fraction": args.top_frac, "features": feats_geo}, ensure_ascii=False))
    for h in args.horizons:
        models[h].save_model(str(outputs / "models" / f"fire_h{h}_{dates[T].date()}.txt"))
    metrics["prediksi_terakhir"] = {"tanggal_terbit": str(dates[T].date()), "n_sel": int(len(out)), "harapan_sel_berapi_p1": round(float(out[first].sum()), 2)}
    (outputs / "fire_metrics.json").write_text(json.dumps(metrics, indent=1, ensure_ascii=False))
    print(f"\nprediksi terbit {dates[T].date()}: harapan sel berapi besok {out[first].sum():.1f} dari {len(out):,} sel | sel teratas {len(top)} -> outputs/fire_top_cells.geojson")
    print("gerbang kelas kepercayaan:", "SEDANG (lolos uji retrospektif)" if all_ok else "RENDAH (belum mengalahkan pembanding)")


if __name__ == "__main__":
    main()
