"""01_stations: bangun tabel bersih dari `station-detail` (muka air dalam cm).

    python scripts/01_stations.py
Masuk : data/raw/sitmat/details/*.json  (hasil 01b)
Keluar: data/interim/ts_30min.parquet, ts_daily.parquet, stations.parquet

QC ringan (bendera, dan nilai mustahil menjadi NaN; tidak ada stasiun yang dibuang di sini):
  - zona waktu tetap WIB (UTC+7), sesuai petunjuk dari data
  - muka air di luar [-400, +100] cm -> NaN; kelembapan di luar [0, 100] -> NaN
  - hujan negatif atau > 60 mm per 30 menit -> NaN (nilai stasiun tak konsisten; fitur hujan utama memakai CHIRPS)
  - lonjakan muka air > 30 cm per 30 menit diberi bendera `wl_spike`
  - koordinat di luar kotak Indonesia diberi bendera `coord_ok = False`
  - `region` (sumatra/kalimantan/papua/other) dari koordinat; `other` (misalnya di Jawa) dianggap mencurigakan
  - sensor datar di sekitar nol (|median| < 5 cm dan simpangan baku < 5 cm) diberi bendera `flat_sensor = True`
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import path  # noqa: E402
from src.regions import add_region  # noqa: E402
from src.sitmat_parse import station_daily, station_meta, station_timeseries  # noqa: E402

TZ_OFFSET = 7
WL_RANGE = (-400.0, 100.0)
RAIN_MAX = 60.0
SPIKE_CM = 30.0
LON_RANGE, LAT_RANGE = (90.0, 142.0), (-12.0, 7.0)


def load_detail(file: Path) -> dict:
    rec = json.loads(file.read_text(encoding="utf-8"))
    return rec["data"] if {"url", "data"} <= rec.keys() else rec


def clean_30min(ts: pd.DataFrame) -> pd.DataFrame:
    ts = ts.drop_duplicates("ts_local").sort_values("ts_local").reset_index(drop=True)
    wl = ts["water_level_cm"]
    ts.loc[(wl < WL_RANGE[0]) | (wl > WL_RANGE[1]), "water_level_cm"] = np.nan
    ts.loc[~ts["soil_moisture"].between(0, 100), "soil_moisture"] = np.nan
    ts.loc[(ts["rain"] < 0) | (ts["rain"] > RAIN_MAX), "rain"] = np.nan
    ts["wl_spike"] = ts["water_level_cm"].diff().abs() > SPIKE_CM
    return ts


def main() -> None:
    files = sorted((path("raw") / "sitmat" / "details").glob("*_d*.json"))
    if not files:
        sys.exit("Belum ada berkas di data/raw/sitmat/details. Jalankan 01b_scrape_station_details.py dulu.")

    ts_parts, daily_parts, meta_rows, skipped = [], [], [], []
    for file in files:
        try:
            raw = load_detail(file)
            if not (raw.get("properties") or {}).get("properties"):
                skipped.append((file.name, "respons kosong (tanpa properti stasiun)"))
                continue
            meta, ts, daily = station_meta(raw), station_timeseries(raw, tz_offset=TZ_OFFSET), station_daily(raw)
        except (KeyError, TypeError, ValueError) as err:
            skipped.append((file.name, str(err)[:60]))
            continue
        ts = clean_30min(ts)
        valid = ts["water_level_cm"].notna()
        wl_all = pd.concat([ts["water_level_cm"], daily["water_level_cm"].where(daily["water_level_cm"].between(*WL_RANGE))]).dropna()
        lon, lat = meta["lon"], meta["lat"]
        meta.update(
            coord_ok=bool(lon is not None and lat is not None and LON_RANGE[0] <= lon <= LON_RANGE[1]
                          and LAT_RANGE[0] <= lat <= LAT_RANGE[1]),
            n_30min=int(valid.sum()), days_30min=round(valid.sum() / 48, 1),
            wl_valid_frac=round(float(valid.mean()), 3) if len(ts) else 0.0,
            first_ts=ts["ts_local"].min(), last_ts=ts["ts_local"].max(),
            wl_median_cm=float(ts["water_level_cm"].median()) if valid.any() else np.nan,
            wl_std_cm=float(wl_all.std()) if len(wl_all) > 1 else np.nan,
            flat_sensor=bool(len(wl_all) > 1 and abs(wl_all.median()) < 5 and wl_all.std() < 5),
            n_spikes=int(ts["wl_spike"].sum()), n_daily=int(daily["water_level_cm"].notna().sum()),
            daily_first=daily["date"].min() if len(daily) else pd.NaT,
        )
        meta_rows.append(meta)
        ts_parts.append(ts)
        daily_parts.append(daily)

    out = path("interim")
    stations = add_region(pd.DataFrame(meta_rows))
    pd.concat(ts_parts, ignore_index=True).to_parquet(out / "ts_30min.parquet", index=False)
    pd.concat(daily_parts, ignore_index=True).to_parquet(out / "ts_daily.parquet", index=False)
    stations.to_parquet(out / "stations.parquet", index=False)

    print(f"stasiun diproses: {len(stations)} | dilewati: {len(skipped)}")
    print(f"koordinat wajar: {int(stations.coord_ok.sum())}")
    print(f"data 30 menitan >= 14 hari: {int((stations.days_30min >= 14).sum())} | >= 28 hari: {int((stations.days_30min >= 28).sum())}")
    print(f"riwayat harian >= 60 hari: {int((stations.n_daily >= 60).sum())}")
    print("wilayah (semua stasiun):", stations["region"].value_counts().to_dict())
    good = stations[stations.coord_ok & (stations.days_30min >= 14)]
    print("wilayah (koordinat wajar, >= 14 hari):", good["region"].value_counts().to_dict())
    other = stations[stations.coord_ok & ~stations.region_ok & (stations.n_30min + stations.n_daily > 0)]
    if len(other):
        print(f"\nBerkoordinat di luar Sumatra/Kalimantan/Papua ({len(other)} stasiun; dikeluarkan dari pilot dan model):")
        print(other[["station_id", "name", "lon", "lat"]].round(2).to_string(index=False))
    flat = stations[stations.flat_sensor]
    if len(flat):
        print(f"\nSensor datar di sekitar nol ({len(flat)} stasiun; dikeluarkan dari pilot dan model):")
        print(flat[["station_id", "wl_median_cm", "wl_std_cm", "days_30min"]].round(2).to_string(index=False))
    for name, why in skipped[:5]:
        print("dilewati:", name, why)
    print("\nTersimpan di", out)


if __name__ == "__main__":
    main()
