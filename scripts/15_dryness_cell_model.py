"""15_dryness_cell_model: prakiraan pengeringan 7 dan 14 hari per sel 1 km, dilatih di stasiun SiTMAT dan diterapkan ke semua sel (varian tanpa muka air).

    python scripts/15_dryness_cell_model.py [--dynamic data/features/dyn_rain_pixels.parquet data/features/dyn_soil_pixels.parquet data/features/dyn_ndmi_cells.parquet]

Masuk : data/features/model_table.parquet (03: station_id, date, wl_cm), data/interim/stations.parquet, data/features/grid/{static,risk_class,lulc}.tif, fitur dinamis (02g)
Keluar: outputs/dryness_cell_latest.parquet   per sel: perubahan muka air median, q10, q90 (cm) dan peluang turun >= 10 cm untuk 7 dan 14 hari
        outputs/dryness_cells.geojson         poligon sel untuk web
        outputs/dryness_metrics.json          uji RUANG-WAKTU (stasiun baru DAN tanggal baru), pembanding, gerbang bukti

Prinsip konsistensi: fitur sel stasiun diambil dari kubus fitur yang sama dengan sel peta (statis 1 km, hujan dan kelembapan tanah per piksel produk, NDMI komposit),
bukan dari fitur titik stasiun (02), supaya definisi fitur identik. Muka air saat ini TIDAK dipakai sebagai fitur (sel tanpa sensor tidak punya muka air).
Target: perubahan muka air (cm) dalam h hari = wl(t+h) - wl(t); model kuantil LightGBM (q10, q50, q90) dan klasifikasi turun >= 10 cm.
Uji: tahan LIMA kelompok stasiun; latih pada stasiun lain dengan tanggal sebelum titik potong, uji pada stasiun yang ditahan dengan tanggal sesudahnya (jeda h hari).
Pembanding: persistensi (perubahan 0) dan frekuensi dasar. Gerbang: skill MAE terhadap persistensi > 0 pada kedua horizon, cakupan q10-q90 antara 65 dan 95 persen, skill Brier > 0.
Peringatan jujur: hasil sebelumnya pada data nyata menunjukkan pengeringan per stasiun sulit diperkirakan tanpa muka air saat ini; gerbang ini yang menentukan apakah peta boleh
tampil dengan kepercayaan lebih dari "rendah". Hanya 40-an stasiun di beberapa klaster: peta di luar klaster itu adalah ekstrapolasi.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.cells import cell_grid_lonlat, load_dynamic_cubes, load_universe  # noqa: E402
from src.common import path  # noqa: E402
from src.grid import cell_center_lonlat, cell_id, cell_polygon_lonlat, lonlat_to_cell  # noqa: E402
from src.regions import add_region  # noqa: E402

HORIZONS = (7, 14)
DROP_CM = -10.0
BASE = dict(learning_rate=0.05, num_leaves=15, min_data_in_leaf=60, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0,
            verbose=-1, seed=7, deterministic=True, force_row_wise=True)


def station_cells(uni: dict) -> pd.DataFrame:
    st = add_region(pd.read_parquet(path("interim") / "stations.parquet"))
    flat = st["flat_sensor"] if "flat_sensor" in st else False
    st = st[st["coord_ok"] & st["region_ok"] & ~flat].copy()
    cx, cy, _ = lonlat_to_cell(st["lon"].to_numpy(), st["lat"].to_numpy(), 1000)
    st["r"], st["c"] = uni["cy_top"] - cy, cx - uni["cx0"]
    hh, ww = uni["shape"]
    return st[(st.r >= 0) & (st.r < hh) & (st.c >= 0) & (st.c < ww)][["station_id", "r", "c"]].reset_index(drop=True)


def build_samples(wl: pd.DataFrame, stc: pd.DataFrame, feats: dict, dates: pd.DatetimeIndex, names: list) -> pd.DataFrame:
    """Satu baris per (stasiun, tanggal) dengan fitur sel dan target perubahan 7 dan 14 hari."""
    rows = []
    sidx = {s: i for i, s in enumerate(stc["station_id"])}
    piv = wl.pivot_table(index="date", columns="station_id", values="wl_cm").reindex(dates)
    for s, i in sidx.items():
        if s not in piv:
            continue
        r, c = int(stc.r[i]), int(stc.c[i])
        y = piv[s].to_numpy()
        part = {n: np.asarray(feats[n][:, r, c]) for n in names}
        df = pd.DataFrame(part)
        df["station_id"], df["t"] = s, np.arange(len(dates))
        for h in HORIZONS:
            fut = np.full(len(y), np.nan); fut[:-h] = y[h:]
            df[f"y{h}"] = fut - y
        df["wl_now"] = y
        rows.append(df[np.isfinite(y)])
    return pd.concat(rows, ignore_index=True)


def fit_quantiles(X, y, alphas=(0.1, 0.5, 0.9), rounds=250):
    return {a: lgb.train({**BASE, "objective": "quantile", "alpha": a}, lgb.Dataset(X, y), num_boost_round=rounds) for a in alphas}


def fit_drop(X, y_bin, rounds=250):
    return lgb.train({**BASE, "objective": "binary"}, lgb.Dataset(X, y_bin), num_boost_round=rounds)


def predict_q(models, X):
    q = np.sort(np.column_stack([models[a].predict(X) for a in (0.1, 0.5, 0.9)]), axis=1)    # urut: q10 <= median <= q90
    return q[:, 0], q[:, 1], q[:, 2]


def evaluate(samples: pd.DataFrame, names: list, n_folds: int, rng) -> dict:
    """Uji ruang-waktu: stasiun yang ditahan DAN tanggal sesudah titik potong; latih hanya pada stasiun lain dan tanggal sebelum (dikurangi jeda)."""
    stations = np.array(sorted(samples["station_id"].unique()))
    rng.shuffle(stations)
    folds = np.array_split(stations, min(n_folds, len(stations)))
    T = int(samples["t"].max())
    cutoff = int(samples["t"].min() + 0.7 * (T - samples["t"].min()))
    out = {}
    pooled = {h: {"p": [], "y": []} for h in HORIZONS}
    for h in HORIZONS:
        parts = []
        for hold in folds:
            tr = samples[~samples.station_id.isin(hold) & (samples.t <= cutoff - h) & samples[f"y{h}"].notna()]
            te = samples[samples.station_id.isin(hold) & (samples.t >= cutoff) & samples[f"y{h}"].notna()]
            if len(tr) < 500 or len(te) < 50:
                continue
            q = fit_quantiles(tr[names], tr[f"y{h}"], rounds=150)
            clf = fit_drop(tr[names], (tr[f"y{h}"] <= DROP_CM).astype(int), rounds=150)
            q10, q50, q90 = predict_q(q, te[names]); p = clf.predict(te[names])
            parts.append(pd.DataFrame({"y": te[f"y{h}"].to_numpy(), "q10": q10, "q50": q50, "q90": q90, "p": p, "base": float((tr[f"y{h}"] <= DROP_CM).mean())}))
        if not parts:
            out[f"h{h}"] = {"catatan": "data terlalu sedikit untuk uji ruang-waktu"}
            continue
        d = pd.concat(parts, ignore_index=True)
        ev = (d["y"] <= DROP_CM).astype(int)
        mae_m, mae_p = float((d["y"] - d["q50"]).abs().mean()), float(d["y"].abs().mean())
        brier_m, brier_b = float(((d["p"] - ev) ** 2).mean()), float(((d["base"] - ev) ** 2).mean())
        out[f"h{h}"] = {"n_uji": int(len(d)), "laju_turun10": round(float(ev.mean()), 4), "mae_model_cm": round(mae_m, 3), "mae_persistensi_cm": round(mae_p, 3),
                        "skill_mae": round(1 - mae_m / mae_p, 4), "cakupan_q10_q90": round(float(((d.y >= d.q10) & (d.y <= d.q90)).mean()), 4),
                        "brier": round(brier_m, 5), "brier_dasar": round(brier_b, 5), "skill_brier": round(1 - brier_m / brier_b, 4),
                        "auc_turun10": round(float(roc_auc_score(ev, d["p"])), 4) if 0 < ev.sum() < len(ev) else None, "titik_potong_t": cutoff}
        pooled[h]["p"], pooled[h]["y"] = d["p"].to_numpy(), ev.to_numpy()
    return out, pooled


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dynamic", nargs="+", default=None)
    ap.add_argument("--folds", type=int, default=5)
    args = ap.parse_args()
    rng = np.random.default_rng(7)
    grid = path("features") / "grid"
    mt_file = path("features") / "model_table.parquet"
    if not mt_file.exists():
        sys.exit("model_table.parquet tidak ada. Jalankan 03_assemble.py dulu.")
    dyn_files = args.dynamic or [str(f) for f in (path("features") / n for n in ("dyn_rain_pixels.parquet", "dyn_soil_pixels.parquet", "dyn_ndmi_cells.parquet")) if f.exists()]
    if not dyn_files:
        sys.exit("Tidak ada fitur dinamis. Jalankan 02f dan 02g dulu (atau beri --dynamic).")
    uni = load_universe(grid)
    wl = pd.read_parquet(mt_file, columns=["station_id", "date", "wl_cm"]).dropna(subset=["wl_cm"])
    wl["date"] = pd.to_datetime(wl["date"])
    dates = pd.date_range(wl["date"].min(), wl["date"].max(), freq="D")
    dyn = load_dynamic_cubes(dyn_files, dates, uni)
    doy = 2 * np.pi * dates.dayofyear.to_numpy() / 365.25
    feats = {k: np.broadcast_to(v[:, None, None], (len(dates),) + uni["shape"]) for k, v in (("doy_sin", np.sin(doy).astype("float32")), ("doy_cos", np.cos(doy).astype("float32")))}
    feats.update({k: np.broadcast_to(a[None], (len(dates),) + uni["shape"]) for k, a in uni["static"].items()})
    feats.update(dyn)
    names = list(feats)
    stc = station_cells(uni)
    samples = build_samples(wl, stc, feats, dates, names)
    usable = samples[names].notna().mean(axis=0)
    names = [n for n in names if usable[n] >= 0.5]                              # buang fitur yang hampir kosong di stasiun
    print(f"stasiun di dalam grid: {stc.station_id.nunique()} | sampel stasiun-hari: {len(samples):,} | fitur ({len(names)}): {names}")
    if samples["station_id"].nunique() < 6:
        sys.exit("Stasiun terlalu sedikit untuk uji ruang-waktu (minimal 6).")

    metrics = {"dibuat": datetime.now(timezone.utc).isoformat(timespec="seconds"), "fitur": names, "n_stasiun": int(samples["station_id"].nunique()), "n_sampel": int(len(samples))}
    ev, pooled = evaluate(samples, names, args.folds, rng)
    metrics["uji_ruang_waktu"] = ev
    for h in HORIZONS:
        e = ev.get(f"h{h}", {})
        print(f"horizon {h:2d} hari | uji n={e.get('n_uji', 0):,} | skill MAE vs persistensi {e.get('skill_mae', float('nan')):+.3f} | cakupan q10-q90 {e.get('cakupan_q10_q90', float('nan')):.0%} | skill Brier {e.get('skill_brier', float('nan')):+.3f}")
    ok = all(ev.get(f"h{h}", {}).get("skill_mae", -1) > 0 and 0.65 <= ev.get(f"h{h}", {}).get("cakupan_q10_q90", 0) <= 0.95 and ev.get(f"h{h}", {}).get("skill_brier", -1) > 0 for h in HORIZONS)
    metrics["skill_ok"], metrics["cap_class"] = bool(ok), 1 if ok else 0
    metrics["catatan"] = "Uji ruang-waktu pada stasiun yang ditahan; ekstrapolasi ke sel di luar klaster stasiun tidak teruji."

    # ---- model akhir (semua stasiun) dan prediksi tanggal terbaru untuk semua sel
    last_t = len(dates) - 1
    valid = uni["valid"]
    Xnow = np.stack([np.asarray(feats[n])[last_t][valid] for n in names], axis=-1).astype("float32")
    rr, cc = np.nonzero(valid)
    cx, cy = uni["cx0"] + cc, uni["cy_top"] - rr
    out = pd.DataFrame({"cell_id": cell_id(cx, cy), "cx": cx, "cy": cy})
    out["lon"], out["lat"] = cell_center_lonlat(cx, cy)
    for h in HORIZONS:
        tr = samples[samples[f"y{h}"].notna()]
        q = fit_quantiles(tr[names], tr[f"y{h}"])
        clf = fit_drop(tr[names], (tr[f"y{h}"] <= DROP_CM).astype(int))
        q10, q50, q90 = predict_q(q, Xnow)
        p = clf.predict(Xnow)
        if len(pooled[h]["p"]) > 200 and 0 < pooled[h]["y"].sum() < len(pooled[h]["y"]):       # kalibrasi isotonik pada prediksi uji ruang-waktu
            p = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(pooled[h]["p"], pooled[h]["y"]).predict(p)
        out[f"d{h}"], out[f"q10_{h}"], out[f"q90_{h}"], out[f"p{h}"] = q50, q10, q90, p
    out["issue_date"] = str(dates[-1].date())
    outputs = path("outputs"); outputs.mkdir(parents=True, exist_ok=True)
    out.to_parquet(outputs / "dryness_cell_latest.parquet", index=False)
    geo = [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [cell_polygon_lonlat(int(r.cx), int(r.cy))]},
            "properties": {k: round(float(getattr(r, k)), 3) for k in ("p7", "p14", "d7", "d14", "q10_14", "q90_14")}} for r in out.itertuples()]
    (outputs / "dryness_cells.geojson").write_text(json.dumps({"type": "FeatureCollection", "issue_date": str(dates[-1].date()), "features": geo}, ensure_ascii=False))
    metrics["prediksi_terakhir"] = {"tanggal_terbit": str(dates[-1].date()), "n_sel": int(len(out)), "p14_rata2": round(float(out["p14"].mean()), 4), "p14_maks": round(float(out["p14"].max()), 4)}
    (outputs / "dryness_metrics.json").write_text(json.dumps(metrics, indent=1, ensure_ascii=False))
    print(f"\nprediksi terbit {dates[-1].date()}: {len(out):,} sel | P(turun>=10 cm, 14 hari) rata-rata {out['p14'].mean():.2f}, maks {out['p14'].max():.2f}")
    print("gerbang:", "SEDANG (lolos uji ruang-waktu)" if ok else "RENDAH (belum mengalahkan pembanding pada stasiun baru dan tanggal baru)")


if __name__ == "__main__":
    main()
