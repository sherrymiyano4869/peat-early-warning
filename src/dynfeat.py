"""Fitur dinamis yang kausal (hanya memakai data sampai tanggal itu) dari deret per piksel atau per sel: hujan, hari tanpa hujan, kelembapan tanah, NDMI.

Anomali dihitung terhadap klimatologi dari TAHUN-TAHUN SEBELUMNYA saja (minimal `min_years`), bukan seluruh rekaman, supaya uji mundur tidak
meminjam informasi masa depan. Akibatnya tahun-tahun awal rekaman tidak punya anomali (NaN).
"""
import numpy as np
import pandas as pd

RAIN_DRY_MM = 1.0   # hari tanpa hujan (HTH) menurut BMKG: hujan < 1 mm


def pivot(df: pd.DataFrame, key: str, value: str, dates: pd.DatetimeIndex):
    """Long (key, date, value) -> larik (hari, kunci) float64 pada rentang tanggal penuh; NaN untuk hari yang tak ada."""
    keys = list(pd.unique(df[key]))
    kidx = {k: i for i, k in enumerate(keys)}
    t = dates.get_indexer(pd.DatetimeIndex(df["date"]))
    ok = t >= 0
    A = np.full((len(dates), len(keys)), np.nan)
    A[t[ok], df[key].map(kidx).to_numpy()[ok]] = df[value].to_numpy(dtype=float)[ok]
    return A, keys


def rolling_sum(A: np.ndarray, w: int, min_frac: float = 0.8) -> np.ndarray:
    """Jumlah w hari terakhir (termasuk hari ini); NaN bila kurang dari min_frac*w hari terisi."""
    v = np.isfinite(A)
    cs, cn = np.cumsum(np.where(v, A, 0.0), axis=0), np.cumsum(v, axis=0)
    S, N = cs.copy(), cn.copy()
    S[w:] -= cs[:-w]
    N[w:] -= cn[:-w]
    out = np.where(N >= min_frac * w, S, np.nan)
    out[: w - 1] = np.nan          # jendela belum penuh di awal rekaman
    return out


def rolling_mean(A: np.ndarray, w: int, min_frac: float = 0.8) -> np.ndarray:
    v = np.isfinite(A)
    cn = np.cumsum(v, axis=0); N = cn.copy(); N[w:] -= cn[:-w]
    return rolling_sum(A, w, min_frac) / np.where(N > 0, N, np.nan)


def dry_day_run(A: np.ndarray, thr: float = RAIN_DRY_MM) -> np.ndarray:
    """Jumlah hari berturut-turut (sampai hari ini) dengan hujan < thr. Hari tanpa data memutus hitungan (NaN)."""
    out = np.full(A.shape, np.nan)
    cnt = np.zeros(A.shape[1])
    for t in range(A.shape[0]):
        r = A[t]
        cnt = np.where(np.isnan(r), np.nan, np.where(r < thr, np.nan_to_num(cnt) + 1, 0.0))
        out[t] = cnt
    return out


def causal_anomaly(A: np.ndarray, groups: np.ndarray, years: np.ndarray, min_years: int = 3, zscore: bool = False) -> np.ndarray:
    """Selisih (atau skor-z) terhadap rata-rata kelompok yang sama (hari dalam tahun atau bulan) dari tahun-tahun SEBELUMNYA."""
    ng = int(groups.max()) + 1
    S, S2, N = np.zeros((ng, A.shape[1])), np.zeros((ng, A.shape[1])), np.zeros((ng, A.shape[1]))
    out = np.full(A.shape, np.nan)
    for y in np.unique(years):
        idx = np.nonzero(years == y)[0]
        g = groups[idx]
        n = N[g]
        with np.errstate(all="ignore"):
            mean = S[g] / n
            var = np.maximum(S2[g] / n - mean ** 2, 1e-12)
            dev = A[idx] - mean
            val = dev / np.sqrt(var) if zscore else dev
        enough = n >= min_years
        out[idx] = np.where(enough, val, np.nan)
        v = np.isfinite(A[idx])
        np.add.at(S, g, np.where(v, A[idx], 0.0)); np.add.at(S2, g, np.where(v, A[idx] ** 2, 0.0)); np.add.at(N, g, v.astype(float))
    return out


def doy_groups(dates: pd.DatetimeIndex) -> np.ndarray:
    return np.minimum(dates.dayofyear.to_numpy(), 365) - 1       # 29 Feb digabung dengan 28 Feb


def rain_features(df: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """df: pixel_id, lon, lat, date, rain_mm -> piksel-hari: rain_1d, rain_7d, rain_14d, rain_30d, dry_days, rain_30d_anom (mm; negatif = defisit)."""
    A, keys = pivot(df, "pixel_id", "rain_mm", dates)
    r30 = rolling_sum(A, 30)
    feats = {"rain_1d": A, "rain_7d": rolling_sum(A, 7), "rain_14d": rolling_sum(A, 14), "rain_30d": r30, "dry_days": dry_day_run(A),
             "rain_30d_anom": causal_anomaly(r30, doy_groups(dates), dates.year.to_numpy())}
    return _to_long(feats, keys, dates, df)


def soil_features(df: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """df: pixel_id, lon, lat, date, soil_moisture (m3/m3) -> soil_moisture, soil_7d, soil_anom_z."""
    A, keys = pivot(df, "pixel_id", "soil_moisture", dates)
    feats = {"soil_moisture": A, "soil_7d": rolling_mean(A, 7), "soil_anom_z": causal_anomaly(A, doy_groups(dates), dates.year.to_numpy(), zscore=True)}
    return _to_long(feats, keys, dates, df)


def ndmi_features(df: pd.DataFrame, min_years: int = 3) -> pd.DataFrame:
    """df: cx, cy, window_start, window_end, ndmi -> sel-jendela: available_from (= window_end), ndmi, ndmi_anom_z (z terhadap bulan sama tahun-tahun sebelumnya)."""
    df = df.copy()
    df["window_end"] = pd.to_datetime(df["window_end"])
    df["cell"] = df["cx"].astype(str) + "_" + df["cy"].astype(str)
    ends = pd.DatetimeIndex(sorted(df["window_end"].unique()))
    A, keys = pivot(df.rename(columns={"window_end": "date"}), "cell", "ndmi", ends)
    z = causal_anomaly(A, ends.month.to_numpy() - 1, ends.year.to_numpy(), min_years=min_years, zscore=True)
    cells = df[["cell", "cx", "cy"]].drop_duplicates("cell").set_index("cell").loc[keys]
    out = pd.DataFrame({"available_from": np.repeat(ends.to_numpy(), len(keys)), "cx": np.tile(cells["cx"].to_numpy(), len(ends)), "cy": np.tile(cells["cy"].to_numpy(), len(ends)),
                        "ndmi": A.ravel(), "ndmi_anom_z": z.ravel()})
    return out.dropna(subset=["ndmi"]).reset_index(drop=True)


def _to_long(feats: dict, keys: list, dates: pd.DatetimeIndex, src: pd.DataFrame) -> pd.DataFrame:
    pos = src[["pixel_id", "lon", "lat"]].drop_duplicates("pixel_id").set_index("pixel_id").loc[keys]
    T, P = len(dates), len(keys)
    out = pd.DataFrame({"date": np.repeat(dates.to_numpy(), P), "lon": np.tile(pos["lon"].to_numpy(), T), "lat": np.tile(pos["lat"].to_numpy(), T)})
    for k, a in feats.items():
        out[k] = a.ravel().astype("float32")
    return out.dropna(subset=list(feats)[:1]).reset_index(drop=True)
