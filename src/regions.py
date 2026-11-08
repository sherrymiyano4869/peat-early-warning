"""Penanda wilayah kasar (pulau gambut utama) dari koordinat; selain itu dianggap `other`."""
import pandas as pd

# (lon_min, lon_maks), (lat_min, lat_maks); kotak kasar, bukan batas administrasi
REGIONS = {
    "sumatra": ((94.5, 108.5), (-6.1, 6.0)),
    "kalimantan": ((108.6, 119.5), (-4.5, 4.6)),
    "papua": ((130.5, 141.5), (-9.5, 0.5)),
}


def region_of(lon, lat) -> str:
    if pd.isna(lon) or pd.isna(lat):
        return "other"
    for name, ((lo0, lo1), (la0, la1)) in REGIONS.items():
        if lo0 <= lon <= lo1 and la0 <= lat <= la1:
            return name
    return "other"


def add_region(st: pd.DataFrame) -> pd.DataFrame:
    """Tambahkan kolom `region` dan `region_ok` (bukan `other`) bila belum ada."""
    st = st.copy()
    if "region" not in st:
        st["region"] = [region_of(x, y) for x, y in zip(st["lon"], st["lat"])]
    st["region_ok"] = st["region"] != "other"
    return st
