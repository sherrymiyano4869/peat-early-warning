"""Ubah respons `station-detail` SiTMAT menjadi metadata dan deret waktu rapi.

Struktur yang dipakai (hasil inspeksi respons nyata):
  properties.properties.detail.ListIOTSensorWaterLevel   [{Tanggal, Jam, WaterLevel}]
  properties.properties.detail.ListIOTSensorSoilMoisture [{Tanggal, Jam, SoilMoisture}]
  properties.properties.detail.ListIOTSensorRainFall     [{Tanggal, Jam, RainFall}]
Daftar `history`, `rows`, dan `ListTableLineData` tidak dipakai (ringkasan harian
dan duplikat, berisi "NaN").
"""
import pandas as pd

DEFAULT_TZ_OFFSET = 7  # WIB

LISTS = {
    "ListIOTSensorWaterLevel": ("WaterLevel", "water_level_cm"),
    "ListIOTSensorSoilMoisture": ("SoilMoisture", "soil_moisture"),
    "ListIOTSensorRainFall": ("RainFall", "rain"),
}


def _props(raw: dict) -> dict:
    return raw["properties"]["properties"]


def station_meta(raw: dict) -> dict:
    p = _props(raw)
    d = p.get("detail", {})
    return {
        "station_id": p.get("station_id") or p.get("Code"),
        "name": p.get("lokasi") or d.get("name"),
        "lat": p.get("latitude"),
        "lon": p.get("longitude"),
        "device_type": d.get("device_type"),
        "source": p.get("source"),
        "provinsi": p.get("provinsi") or None,
        "kabupaten": p.get("kabupaten") or None,
        "kecamatan": p.get("kecamatan") or None,
        "status_now": p.get("status"),
        "last_update_utc": d.get("last_update_at"),
    }


def _list_to_frame(items: list, value_key: str, out_name: str) -> pd.DataFrame:
    if not items:
        return pd.DataFrame(columns=["ts_local", out_name])
    df = pd.DataFrame(items)
    df["ts_local"] = pd.to_datetime(
        df["Tanggal"].astype(str) + " " + df["Jam"].astype(str),
        format="%d-%b-%Y %H:%M",
        errors="coerce",
    )
    df[out_name] = pd.to_numeric(df[value_key], errors="coerce")  # "NaN" dan "" jadi NaN
    return df[["ts_local", out_name]].dropna(subset=["ts_local"]).drop_duplicates("ts_local")


def infer_tz_offset(raw: dict, last_local: pd.Timestamp) -> tuple[int, bool]:
    """Selisih jam lokal terhadap UTC dari `last_update_at`; kembali (offset, terdeteksi)."""
    stamp = _props(raw).get("detail", {}).get("last_update_at")
    if not stamp or pd.isna(last_local):
        return DEFAULT_TZ_OFFSET, False
    utc = pd.to_datetime(stamp, utc=True).tz_localize(None)
    offset = round((last_local - utc).total_seconds() / 3600)
    if offset in (7, 8, 9):
        return int(offset), True
    return DEFAULT_TZ_OFFSET, False


def station_timeseries(raw: dict, tz_offset: int | None = None) -> pd.DataFrame:
    """Deret waktu 30 menitan: station_id, ts_local, ts_utc, water_level_cm, soil_moisture, rain.

    tz_offset: jam lokal terhadap UTC; None = disimpulkan dari last_update_at (default WIB).
    """
    detail = _props(raw).get("detail", {})
    ts = None
    for list_key, (value_key, out_name) in LISTS.items():
        frame = _list_to_frame(detail.get(list_key, []), value_key, out_name)
        ts = frame if ts is None else ts.merge(frame, on="ts_local", how="outer")
    ts = ts.sort_values("ts_local").reset_index(drop=True)
    offset = tz_offset if tz_offset is not None else infer_tz_offset(raw, ts["ts_local"].max())[0]
    ts["ts_utc"] = ts["ts_local"] - pd.Timedelta(hours=offset)
    ts.insert(0, "station_id", station_meta(raw)["station_id"])
    return ts


def station_daily(raw: dict) -> pd.DataFrame:
    """Ringkasan harian dari `history`: satu nilai muka air (cm) per hari, hingga sesuai `days`."""
    items = _props(raw).get("history", [])
    df = pd.DataFrame(items)
    if df.empty:
        return pd.DataFrame(columns=["station_id", "date", "water_level_cm", "status_label"])
    out = pd.DataFrame({
        "station_id": station_meta(raw)["station_id"],
        "date": pd.to_datetime(df.get("date"), errors="coerce"),
        "water_level_cm": pd.to_numeric(df.get("water_level"), errors="coerce"),
        "status_label": df.get("status_label"),
    })
    return out.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
