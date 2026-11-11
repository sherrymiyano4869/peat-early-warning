"""09b_export_timeseries: deret waktu rata-rata area pilot untuk halaman Monitoring (webmap/data/timeseries.json).

    python scripts/09b_export_timeseries.py [--years 3]

Masuk (semua opsional; deret yang berkasnya belum ada ditulis dengan status "belum tersedia"):
    data/features/model_table.parquet            muka air stasiun (03)
    data/features/dyn_rain_pixels.parquet        hujan 30 hari dan hari tanpa hujan per piksel GSMaP (02g)
    data/features/dyn_soil_pixels.parquet        kelembapan tanah ERA5-Land per piksel (02g)
    data/features/dyn_ndmi_cells.parquet         NDMI komposit per sel 1 km (02g)
    data/interim/hotspots.parquet                titik api VIIRS bersih (13)
    data/features/grid/grid_meta.json            batas grid pilot (07)
Keluar: webmap/data/timeseries.json  (dibaca webmap/timeseries.js; jalankan SETELAH 09_export_web.py)

Semua deret adalah ringkasan AREA (rata-rata atau median seluruh grid pilot), bukan nilai per sel. "Normal" = rata-rata hari-ke-n pada tahun-tahun
sebelum tahun berjalan, dihaluskan 15 hari; hanya dihitung bila ada >= 3 tahun sebelumnya. Kelembapan tanah ERA5-Land adalah keluaran model reanalisis
untuk tanah mineral, bukan pengamatan gambut. Berkas lokal (tidak ada di zip web).
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import path  # noqa: E402
from src.grid import to_grid  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def grid_bounds():
    f = path("features") / "grid" / "grid_meta.json"
    if not f.exists():
        return None
    m = json.loads(f.read_text())
    return m["x0"], m["y_top"] - m["height"] * m["res_m"], m["x0"] + m["width"] * m["res_m"], m["y_top"]


def in_grid(lon, lat, b):
    if b is None:
        return np.ones(len(lon), dtype=bool)
    x, y = to_grid(np.asarray(lon, dtype=float), np.asarray(lat, dtype=float))
    return (x >= b[0]) & (x <= b[2]) & (y >= b[1]) & (y <= b[3])


def normal_by_doy(s: pd.Series, min_years: int = 3):
    """Rata-rata per hari-ke-n dari tahun-tahun sebelum tahun terakhir (dihaluskan 15 hari, melingkar). None bila riwayat kurang."""
    last_year = s.index.max().year
    hist = s[s.index.year < last_year].dropna()
    if hist.index.year.nunique() < min_years:
        return None, None
    clim = hist.groupby(hist.index.day_of_year).mean().reindex(range(1, 367)).interpolate(limit_direction="both")
    ext = pd.concat([clim.iloc[-15:], clim, clim.iloc[:15]])
    smooth = ext.rolling(15, center=True, min_periods=1).mean().iloc[15:-15]
    smooth.index = range(1, 367)
    years = f"{hist.index.year.min()}–{hist.index.year.max()}"
    return smooth, years


def pack(s: pd.Series, digits: int):
    return [None if pd.isna(v) else round(float(v), digits) for v in s.to_numpy()]


def series(sid, title, unit, s, digits, kind="line", ref=None, ref_label=None, note="", dry_dir=None):
    out = {"id": sid, "title": title, "unit": unit, "kind": kind, "status": "tersedia", "note": note,
           "dates": [d.strftime("%Y-%m-%d") for d in s.index], "values": pack(s, digits)}
    if ref is not None:
        out["ref"] = pack(ref, digits)
        out["ref_label"] = ref_label
    if dry_dir:
        out["dry_dir"] = dry_dir          # "down" = makin kecil makin kering; "up" = makin besar makin kering
    return out


def missing(sid, title, unit, how):
    return {"id": sid, "title": title, "unit": unit, "kind": "line", "status": "belum tersedia", "note": how, "dates": [], "values": []}


def daily_area(f: Path, col: str, start, how="mean"):
    d = pd.read_parquet(f, columns=["date", col])
    d["date"] = pd.to_datetime(d["date"])
    s = d.groupby("date")[col].agg(how).sort_index()
    return s, s[s.index >= start]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--years", type=float, default=3.0, help="panjang deret harian yang diekspor (tahun)")
    ap.add_argument("--out", default=str(ROOT / "webmap" / "data"))
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    feat = path("features")
    b = grid_bounds()
    today = pd.Timestamp(datetime.now(timezone.utc).date())
    start = today - pd.Timedelta(days=int(args.years * 365.25))
    items = []

    # 1. muka air: median stasiun di dalam grid pilot
    f = feat / "model_table.parquet"
    if f.exists():
        m = pd.read_parquet(f, columns=["station_id", "date", "wl_cm", "lon", "lat"])
        m = m[in_grid(m["lon"], m["lat"], b)].dropna(subset=["wl_cm"])
        m["date"] = pd.to_datetime(m["date"])
        if len(m):
            g = m.groupby("date")["wl_cm"]
            n = g.count()
            s = g.median()[n >= 3].sort_index()           # median hanya bila >= 3 stasiun melapor hari itu
            s = s.reindex(pd.date_range(s.index.min(), s.index.max()))
            items.append(series("wl", "Muka air gambut (median stasiun)", "cm", s, 1, dry_dir="down",
                                note=f"Median {m['station_id'].nunique()} stasiun SiTMAT di area pilot; negatif = di bawah permukaan tanah. Data stasiun baru ada sejak {s.index.min().date()}."))
            items[-1]["threshold"] = {"value": -40, "label": "ambang −40 cm"}
    if not any(i["id"] == "wl" for i in items):
        items.append(missing("wl", "Muka air gambut (median stasiun)", "cm", "Jalankan 01 dan 03."))

    # 2-3. hujan 30 hari dan hari tanpa hujan (GSMaP)
    f = feat / "dyn_rain_pixels.parquet"
    if f.exists():
        full, s = daily_area(f, "rain_30d", start)
        clim, yrs = normal_by_doy(full)
        ref = None if clim is None else pd.Series(clim.reindex(s.index.day_of_year).to_numpy(), index=s.index)
        items.append(series("rain30", "Hujan 30 hari terakhir", "mm", s, 0, ref=ref, ref_label=f"normal {yrs}" if yrs else None, dry_dir="down",
                            note="Jumlah hujan GSMaP 30 hari, rata-rata area pilot."))
        _, s = daily_area(f, "dry_days", start)
        items.append(series("dry", "Hari tanpa hujan berturut-turut", "hari", s, 1, dry_dir="up", note="Rata-rata area pilot dari piksel GSMaP (0,1°)."))
    else:
        items.append(missing("rain30", "Hujan 30 hari terakhir", "mm", "Jalankan 02f (gsmap) lalu 02g."))

    # 4. kelembapan tanah (ERA5-Land)
    f = feat / "dyn_soil_pixels.parquet"
    if f.exists():
        full, s = daily_area(f, "soil_moisture", start)
        clim, yrs = normal_by_doy(full)
        ref = None if clim is None else pd.Series(clim.reindex(s.index.day_of_year).to_numpy(), index=s.index)
        items.append(series("soil", "Kelembapan tanah 0–7 cm", "m³/m³", s, 3, ref=ref, ref_label=f"normal {yrs}" if yrs else None, dry_dir="down",
                            note="ERA5-Land (model reanalisis tanah mineral, bukan pengamatan gambut); tertinggal sekitar 9 hari."))
    else:
        items.append(missing("soil", "Kelembapan tanah 0–7 cm", "m³/m³", "Jalankan 02f (era5soil) lalu 02g."))

    # 5. NDMI Sentinel-2 (per jendela komposit)
    f = feat / "dyn_ndmi_cells.parquet"
    if f.exists():
        d = pd.read_parquet(f, columns=["available_from", "ndmi"])
        d["available_from"] = pd.to_datetime(d["available_from"])
        s = d.groupby("available_from")["ndmi"].mean().sort_index()
        s = s[s.index >= start]
        items.append(series("ndmi", "NDMI vegetasi (Sentinel-2)", "indeks", s, 3, dry_dir="down",
                            note="Komposit 30 hari, rata-rata area pilot; titik = akhir jendela. Makin rendah makin kering."))
    else:
        items.append(missing("ndmi", "NDMI vegetasi (Sentinel-2)", "indeks", "Jalankan 02f (ndmi) lalu 02g."))

    # 6. titik api VIIRS per hari
    f = path("interim") / "hotspots.parquet"
    if f.exists() and len(pd.read_parquet(f, columns=["date"])):
        h = pd.read_parquet(f, columns=["date", "lon", "lat"])
        h = h[in_grid(h["lon"], h["lat"], b)]
        h["date"] = pd.to_datetime(h["date"])
        if len(h):
            cnt = h.groupby("date").size()
            idx = pd.date_range(max(start, cnt.index.min()), cnt.index.max())
            s = cnt.reindex(idx, fill_value=0).astype(float)
            items.append(series("hotspot", "Titik api VIIRS per hari", "titik", s, 0, kind="bar", dry_dir="up",
                                note="Deteksi Suomi NPP 375 m di area pilot; tidak terdeteksi bukan berarti tidak ada api (awan dan asap menutup)."))
    if not any(i["id"] == "hotspot" for i in items):
        items.append(missing("hotspot", "Titik api VIIRS per hari", "titik", "Belum ada data FIRMS: isi FIRMS_MAP_KEY, jalankan 12 dan 13 (./run_pipeline.sh titikapi)."))

    order = ["wl", "rain30", "dry", "soil", "ndmi", "hotspot"]
    items.sort(key=lambda i: order.index(i["id"]))
    doc = {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "area": "rata-rata area pilot (seluruh grid)", "series": items}
    (out_dir / "timeseries.json").write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for i in items:
        rng = f"{i['dates'][0]}..{i['dates'][-1]} ({len(i['dates'])} nilai)" if i["dates"] else i["note"]
        print(f"  {i['id']:8s} {i['status']:15s} {rng}")
    print("Tersimpan:", out_dir / "timeseries.json")


if __name__ == "__main__":
    main()
