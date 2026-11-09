"""Fungsi bantu murni-Python untuk 02_gee_features (bisa diuji tanpa Earth Engine)."""
import re
from datetime import date, timedelta

import pandas as pd


def date_chunks(start: date, end: date, max_days: int) -> list:
    """Pecah rentang [start, end] (inklusif) menjadi potongan paling banyak max_days hari."""
    chunks, cur = [], start
    while cur <= end:
        stop = min(cur + timedelta(days=max_days - 1), end)
        chunks.append((cur, stop))
        cur = stop + timedelta(days=1)
    return chunks


def date_windows(start: date, end: date, step_days: int) -> list:
    """Jendela [awal, akhir) selebar step_days yang menutup start..end."""
    windows, cur = [], start
    while cur <= end:
        windows.append((cur, cur + timedelta(days=step_days)))
        cur += timedelta(days=step_days)
    return windows


def parse_daily_bands(features: list, band: str) -> pd.DataFrame:
    """Hasil reduceRegions pada ImageCollection.toBands(): properti 'YYYYMMDD_<band>' -> tabel panjang."""
    pattern = re.compile(rf"^(\d{{8}})_{re.escape(band)}$")
    rows = []
    for feat in features:
        props = feat.get("properties", {})
        for key, value in props.items():
            match = pattern.match(key)
            if match and value is not None:
                rows.append({"station_id": props["station_id"],
                             "date": pd.to_datetime(match.group(1), format="%Y%m%d"), band: value})
    return pd.DataFrame(rows, columns=["station_id", "date", band])


def parse_window_bands(features: list, names: list, fallback_key: str = None) -> pd.DataFrame:
    """Properti 'w<YYYYMMDD>_<nama>' -> tabel lebar per (stasiun, awal jendela).

    Untuk citra satu band, reduceRegions menamai hasil dengan nama reducer ('mean'/'first'), bukan nama band.
    Bila `fallback_key` (mis. 'w20260812') diberikan dan hanya ada satu nama, properti itu dipakai.
    """
    pattern = re.compile(rf"^w(\d{{8}})_({'|'.join(re.escape(n) for n in names)})$")
    single = fallback_key if len(names) == 1 else None
    rows = {}
    for feat in features:
        props = feat.get("properties", {})
        for key, value in props.items():
            match = pattern.match(key)
            if match:
                rows.setdefault((props["station_id"], match.group(1)), {})[match.group(2)] = value
            elif single and key in ("mean", "first") and value is not None:
                rows.setdefault((props["station_id"], single[1:]), {})[names[0]] = value
    records = [{"station_id": sid, "window_start": pd.to_datetime(d, format="%Y%m%d"), **vals}
               for (sid, d), vals in rows.items()]
    return pd.DataFrame(records, columns=["station_id", "window_start", *names])
