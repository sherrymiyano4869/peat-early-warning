"""Kubus sel 1 km (hari x baris x kolom) di grid induk: semesta sel, titik api, dan pemuat fitur dinamis dalam empat format.

Format berkas fitur dinamis (parquet), dikenali dari kolomnya:
  sel-hari      date, cx, cy, fitur...                  nilai per sel 1 km per hari
  piksel-hari   date, lon, lat, fitur...                nilai per piksel produk (mis. GSMaP, ERA5-Land 0,1 derajat); tiap sel mengambil piksel terdekat
  regional      date, fitur...                          satu deret untuk seluruh wilayah (mis. ENSO, DMI)
  sel-jendela   available_from, cx, cy, fitur...        komposit per jendela (mis. NDMI bulanan); berlaku mulai `available_from` dan diteruskan
                                                        ke hari-hari berikutnya sampai jendela berikutnya (tanpa melihat ke depan)
Pembuat berkas bertanggung jawab agar nilai pada tanggal t hanya memakai data yang sudah diketahui pada t.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from scipy.spatial import cKDTree

from src.grid import cell_center_lonlat, cell_from_id

STATIC_FEATS = {"canal_kde_250m": "mean", "canal_kde_500m": "mean", "fabdem_relief_1km": "mean", "fabdem_elev_m": "mean"}
LULC_FRAC = {10: "tree", 20: "shrub", 30: "grass", 40: "crop", 60: "bare", 90: "wetland"}   # air, terbangun, bakau sudah dikeluarkan oleh penutup


def load_universe(grid_dir: Path) -> dict:
    """Semesta sel 1 km dari grid 100 m: penutup sah, fitur statis rata-rata blok, dan pecahan tutupan lahan (bila lulc.tif ada)."""
    meta = json.loads((grid_dir / "grid_meta.json").read_text())
    res = float(meta["res_m"])
    if 1000 % res:
        raise SystemExit("Resolusi grid tidak membagi 1000 m.")
    f = int(round(1000 / res))
    with rasterio.open(grid_dir / "static.tif") as s:
        bands = {n: s.read(i + 1).astype("float64") for i, n in enumerate(s.descriptions)}
        H, W = s.height, s.width
    if H % f or W % f:
        raise SystemExit("Grid 100 m belum bersarang di 1 km (jalankan 07_grid_static.py --crs master).")
    hh, ww = H // f, W // f

    def blk(a):
        with np.errstate(all="ignore"):
            return np.nanmean(a.reshape(hh, f, ww, f), axis=(1, 3))

    valid_fine = np.ones((H, W), bool)
    if (grid_dir / "risk_class.tif").exists():
        with rasterio.open(grid_dir / "risk_class.tif") as s:
            valid_fine = s.read(1) > 0
    valid = valid_fine.reshape(hh, f, ww, f).mean(axis=(1, 3)) >= 0.5
    feats = {k: blk(np.where(valid_fine, bands[k], np.nan)).astype("float32") for k in STATIC_FEATS if k in bands}
    if (grid_dir / "lulc.tif").exists():
        with rasterio.open(grid_dir / "lulc.tif") as s:
            lb = {n: s.read(i + 1).astype("float64") for i, n in enumerate(s.descriptions)}
        for code, name in LULC_FRAC.items():
            if f"frac_{code}" in lb:
                feats[f"lulc_{name}"] = blk(lb[f"frac_{code}"]).astype("float32")
    cx0, cy_top = int(round(meta["x0"] / 1000)), int(round(meta["y_top"] / 1000)) - 1
    return {"valid": valid, "static": feats, "cx0": cx0, "cy_top": cy_top, "shape": (hh, ww)}


def cell_grid_lonlat(uni: dict):
    """lon/lat pusat tiap sel (hh, ww)."""
    hh, ww = uni["shape"]
    rr, cc = np.indices((hh, ww))
    return cell_center_lonlat(uni["cx0"] + cc, uni["cy_top"] - rr)


def counts_cube(cell_day: pd.DataFrame, dates: pd.DatetimeIndex, uni: dict):
    hh, ww = uni["shape"]
    cx, cy = cell_from_id(cell_day["cell_id"].to_numpy())
    r, c = uni["cy_top"] - cy, cx - uni["cx0"]
    t = dates.get_indexer(pd.DatetimeIndex(cell_day["date"]))
    ok = (r >= 0) & (r < hh) & (c >= 0) & (c < ww) & (t >= 0)
    cube = np.zeros((len(dates), hh, ww), dtype=np.int16)
    np.add.at(cube, (t[ok], r[ok], c[ok]), cell_day["n"].to_numpy()[ok].astype(np.int16))
    return cube, int((~ok).sum())


def _feature_cols(df: pd.DataFrame, skip) -> list:
    return [c for c in df.columns if c not in skip and pd.api.types.is_numeric_dtype(df[c])]


def load_dynamic_cubes(files, dates: pd.DatetimeIndex, uni: dict, max_pixel_km: float = 20.0) -> dict:
    """Muat berkas fitur dinamis (semua format) menjadi kubus (hari, baris, kolom) float32, NaN bila tak ada nilai."""
    hh, ww = uni["shape"]
    T = len(dates)
    out = {}
    lon_c, lat_c = cell_grid_lonlat(uni)
    for file in files:
        df = pd.read_parquet(file)
        has = set(df.columns)
        if "available_from" in has and {"cx", "cy"} <= has:                                    # sel-jendela
            df["available_from"] = pd.to_datetime(df["available_from"])
            cols = _feature_cols(df, {"available_from", "cx", "cy", "cell_id"})
            wins = np.sort(df["available_from"].unique())
            widx = np.searchsorted(wins, dates.to_numpy(), side="right") - 1           # jendela terakhir yang sudah tersedia pada hari itu
            r, c = uni["cy_top"] - df["cy"].to_numpy(), df["cx"].to_numpy() - uni["cx0"]
            w = np.searchsorted(wins, df["available_from"].to_numpy())
            ok = (r >= 0) & (r < hh) & (c >= 0) & (c < ww)
            for col in cols:
                V = np.full((len(wins) + 1, hh, ww), np.nan, dtype="float32")
                V[w[ok], r[ok], c[ok]] = df[col].to_numpy()[ok]
                out[col] = V[np.where(widx >= 0, widx, len(wins))]                           # -1 -> baris NaN terakhir
        elif "date" in has and {"cx", "cy"} <= has:                                            # sel-hari
            df["date"] = pd.to_datetime(df["date"])
            cols = _feature_cols(df, {"date", "cx", "cy", "cell_id"})
            t = dates.get_indexer(df["date"])
            r, c = uni["cy_top"] - df["cy"].to_numpy(), df["cx"].to_numpy() - uni["cx0"]
            ok = (r >= 0) & (r < hh) & (c >= 0) & (c < ww) & (t >= 0)
            for col in cols:
                a = np.full((T, hh, ww), np.nan, dtype="float32")
                a[t[ok], r[ok], c[ok]] = df[col].to_numpy()[ok]
                out[col] = a
        elif "date" in has and {"lon", "lat"} <= has:                                          # piksel-hari
            df["date"] = pd.to_datetime(df["date"])
            cols = _feature_cols(df, {"date", "lon", "lat", "pixel_id"})
            pix = df[["lon", "lat"]].drop_duplicates().reset_index(drop=True)
            pid = {(round(a, 6), round(b, 6)): i for i, (a, b) in enumerate(zip(pix.lon, pix.lat))}
            tree = cKDTree(pix[["lon", "lat"]].to_numpy())
            dist, nn = tree.query(np.column_stack([lon_c.ravel(), lat_c.ravel()]))
            far = dist * 111.0 > max_pixel_km
            nn = np.where(far, len(pix), nn).reshape(hh, ww)                                  # indeks len(pix) = kolom NaN
            t = dates.get_indexer(df["date"])
            p = np.array([pid[(round(a, 6), round(b, 6))] for a, b in zip(df.lon, df.lat)])
            ok = t >= 0
            for col in cols:
                A = np.full((T, len(pix) + 1), np.nan, dtype="float32")
                A[t[ok], p[ok]] = df[col].to_numpy()[ok]
                out[col] = A[:, nn]
        elif "date" in has:                                                                    # regional
            df["date"] = pd.to_datetime(df["date"])
            cols = _feature_cols(df, {"date"})
            t = dates.get_indexer(df["date"])
            ok = t >= 0
            for col in cols:
                v = np.full(T, np.nan, dtype="float32")
                v[t[ok]] = df[col].to_numpy()[ok]
                out[col] = np.broadcast_to(v[:, None, None], (T, hh, ww))
        else:
            raise SystemExit(f"Format fitur dinamis tidak dikenali: {file} (kolom {sorted(has)[:8]})")
    return out
