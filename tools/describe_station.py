"""Ringkas satu respons station-detail: rentang waktu, kelengkapan, dan statistik.

    python scripts/describe_station.py /tmp/station.json
Bisa juga dipakai pada berkas cache PoliteClient (data/raw/sitmat/*.json).
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.sitmat_parse import infer_tz_offset, station_meta, station_timeseries  # noqa: E402

VARS = ["water_level_cm", "soil_moisture", "rain"]


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Pemakaian: python scripts/describe_station.py berkas.json")
    raw = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if isinstance(raw, dict) and {"url", "fetched_at", "data"} <= raw.keys():
        raw = raw["data"]

    meta, ts = station_meta(raw), station_timeseries(raw)
    offset, detected = infer_tz_offset(raw, ts["ts_local"].max())

    print("== Metadata")
    for key, value in meta.items():
        print(f"  {key:<16} {value}")
    print(f"  zona waktu       UTC+{offset} ({'terdeteksi dari last_update_at' if detected else 'asumsi WIB'})")

    step = ts["ts_local"].diff().dropna()
    print("\n== Waktu")
    print(f"  baris            {len(ts)}")
    print(f"  rentang (lokal)  {ts['ts_local'].min()} -> {ts['ts_local'].max()}")
    print(f"  selang median    {step.median()}  | selang terpanjang {step.max()}")
    expected = int((ts["ts_local"].max() - ts["ts_local"].min()) / step.median()) + 1
    print(f"  kelengkapan      {len(ts)}/{expected} titik = {len(ts) / expected:.1%}")

    print("\n== Nilai kosong")
    for name in VARS:
        print(f"  {name:<16} {ts[name].isna().mean():.1%}")

    print("\n== Statistik")
    print(ts[VARS].describe().round(2).to_string())

    rain = ts["rain"].dropna()
    if len(rain):
        delta = rain.diff().dropna()
        print("\n== Cek satuan hujan")
        print(f"  nilai > 0        {(rain > 0).sum()} titik | maks {rain.max()}")
        print(f"  selisih naik     {(delta > 0).sum()} | turun {(delta < 0).sum()}")
        print("  tafsir: turun jauh lebih sedikit dari naik = kemungkinan kumulatif (turun = reset);")
        print("          naik dan turun kira-kira sama = nilai per selang waktu.")

    jump = ts["water_level_cm"].diff().abs()
    print("\n== Muka air")
    print(f"  lompatan terbesar {jump.max()} cm per selang")


if __name__ == "__main__":
    main()
