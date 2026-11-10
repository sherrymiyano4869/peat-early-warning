"""02g_dynamic_features: fitur dinamis kausal per piksel dan per sel dari data mentah 02f, plus keadaan terbaru pada grid 100 m (dynamic.tif) untuk 08.

    python scripts/02g_dynamic_features.py

Masuk : data/features/grid_dynamic/{rain_pixels,soil_pixels,ndmi_cells}.parquet (02f); grid_meta.json (07)
Keluar: data/features/dyn_enso_daily.parquet   date, nino34, oni, dmi (regional; nilai bulan sebelumnya; butuh 02b)
        data/features/dyn_rain_pixels.parquet   date, lon, lat, rain_1d, rain_7d, rain_14d, rain_30d, dry_days, rain_30d_anom
        data/features/dyn_soil_pixels.parquet   date, lon, lat, soil_moisture, soil_7d, soil_anom_z
        data/features/dyn_ndmi_cells.parquet    available_from, cx, cy, ndmi, ndmi_anom_z
        data/features/grid/dynamic.tif          dry_days, rain_deficit_mm, soil_moisture_dry, ndmi_dryness pada nilai terbaru (lebih besar = lebih kering)
        data/features/grid/dynamic_meta.json    tanggal terbaru dan cakupan tiap pita
        data/features/grid/dynamic_reference.json  100 kuantil historis tiap pita (acuan peringkat untuk 08)
Fitur ini dipakai 14_fire_model.py lewat --dynamic (tiga berkas pertama) dan 15_dryness_cell_model.py.

Kausal: anomali memakai klimatologi dari tahun-tahun SEBELUMNYA saja (minimal 3 tahun; tahun awal rekaman tanpa anomali); komposit NDMI berlaku setelah jendelanya
berakhir. Hari tanpa hujan (HTH) = hari berturut-turut dengan hujan < 1 mm (definisi BMKG), sama dengan fitur stasiun.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import dynfeat  # noqa: E402
from src.common import path  # noqa: E402
from src.enso import lagged_for_dates  # noqa: E402
from src.grid import from_grid, grid_crs  # noqa: E402

BANDS = ["dry_days", "rain_deficit_mm", "soil_moisture_dry", "ndmi_dryness"]
MAX_PIXEL_KM = 20.0


def latest_by_pixel(df: pd.DataFrame, col: str, date_col: str = "date"):
    """Nilai kolom pada tanggal terbaru yang tersedia di produk itu: (tanggal, lon, lat, nilai)."""
    last = df[date_col].max()
    sub = df[df[date_col] == last].dropna(subset=[col])
    return last, sub["lon"].to_numpy(), sub["lat"].to_numpy(), sub[col].to_numpy(dtype=float)


def pixels_to_grid(lon_p, lat_p, val_p, lon_g, lat_g, shape) -> np.ndarray:
    tree = cKDTree(np.column_stack([lon_p, lat_p]))
    dist, nn = tree.query(np.column_stack([lon_g.ravel(), lat_g.ravel()]))
    out = val_p[nn].astype("float32")
    out[dist * 111.0 > MAX_PIXEL_KM] = np.nan
    return out.reshape(shape)


def main() -> None:
    raw = path("features") / "grid_dynamic"
    grid = path("features") / "grid"
    out_dir = path("features")
    meta = json.loads((grid / "grid_meta.json").read_text())
    res, shape = float(meta["res_m"]), (int(meta["height"]), int(meta["width"]))
    cols, rows = np.meshgrid(np.arange(shape[1]), np.arange(shape[0]))
    lon_g, lat_g = from_grid(meta["x0"] + (cols + 0.5) * res, meta["y_top"] - (rows + 0.5) * res)
    bands, info, reference = {}, {}, {}

    if (raw / "rain_pixels.parquet").exists():
        df = pd.read_parquet(raw / "rain_pixels.parquet"); df["date"] = pd.to_datetime(df["date"])
        dates = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
        rf = dynfeat.rain_features(df, dates)
        rf.to_parquet(out_dir / "dyn_rain_pixels.parquet", index=False)
        last, lo, la, dry = latest_by_pixel(rf, "dry_days"); _, lo2, la2, an = latest_by_pixel(rf.dropna(subset=["rain_30d_anom"]), "rain_30d_anom") if rf["rain_30d_anom"].notna().any() else (None, [], [], [])
        bands["dry_days"] = pixels_to_grid(lo, la, dry, lon_g, lat_g, shape)
        info["dry_days"] = {"tanggal": str(last.date()), "sumber": "GSMaP v8 operasional"}
        reference["dry_days"] = np.nanpercentile(rf["dry_days"].to_numpy(dtype=float), np.linspace(0, 100, 101)).tolist()
        if len(an):
            bands["rain_deficit_mm"] = pixels_to_grid(lo2, la2, -an, lon_g, lat_g, shape)       # positif = defisit hujan 30 hari terhadap klimatologi
            info["rain_deficit_mm"] = {"tanggal": str(_.date()), "sumber": "GSMaP, 30 hari, anomali kausal"}
            reference["rain_deficit_mm"] = np.nanpercentile(-rf["rain_30d_anom"].to_numpy(dtype=float), np.linspace(0, 100, 101)).tolist()
        print(f"hujan: {len(rf):,} piksel-hari | HTH terbaru {last.date()} | anomali tersedia: {bool(len(an))}")
    else:
        print("rain_pixels.parquet tidak ada (jalankan 02f --only gsmap).")

    if (raw / "soil_pixels.parquet").exists():
        df = pd.read_parquet(raw / "soil_pixels.parquet"); df["date"] = pd.to_datetime(df["date"])
        dates = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
        sf = dynfeat.soil_features(df, dates)
        sf.to_parquet(out_dir / "dyn_soil_pixels.parquet", index=False)
        if sf["soil_anom_z"].notna().any():
            last, lo, la, z = latest_by_pixel(sf.dropna(subset=["soil_anom_z"]), "soil_anom_z")
            bands["soil_moisture_dry"] = pixels_to_grid(lo, la, -z, lon_g, lat_g, shape)
            info["soil_moisture_dry"] = {"tanggal": str(last.date()), "sumber": "ERA5-Land lapisan 0-7 cm (reanalisis, bukan pengamatan gambut)"}
            reference["soil_moisture_dry"] = np.nanpercentile(-sf["soil_anom_z"].to_numpy(dtype=float), np.linspace(0, 100, 101)).tolist()
        print(f"kelembapan tanah: {len(sf):,} piksel-hari | terbaru {sf['date'].max().date()}")

    if (raw / "ndmi_cells.parquet").exists():
        df = pd.read_parquet(raw / "ndmi_cells.parquet")
        nf = dynfeat.ndmi_features(df)
        nf.to_parquet(out_dir / "dyn_ndmi_cells.parquet", index=False)
        ok = nf.dropna(subset=["ndmi_anom_z"])
        if len(ok):
            last_w = ok.groupby(["cx", "cy"])["available_from"].transform("max") == ok["available_from"]
            cur = ok[last_w]
            cx0, cy_top = int(round(meta["x0"] / 1000)), int(round(meta["y_top"] / 1000)) - 1
            f = int(round(1000 / res))
            hh, ww = shape[0] // f, shape[1] // f
            arr = np.full((hh, ww), np.nan, dtype="float32")
            r, c = cy_top - cur["cy"].to_numpy(), cur["cx"].to_numpy() - cx0
            okk = (r >= 0) & (r < hh) & (c >= 0) & (c < ww)
            arr[r[okk], c[okk]] = -cur["ndmi_anom_z"].to_numpy()[okk]
            bands["ndmi_dryness"] = np.kron(arr, np.ones((f, f), dtype="float32"))[: shape[0], : shape[1]]
            info["ndmi_dryness"] = {"tanggal": str(cur["available_from"].max().date()), "sumber": "Sentinel-2 NDMI komposit, anomali kausal"}
            reference["ndmi_dryness"] = np.nanpercentile(-ok["ndmi_anom_z"].to_numpy(dtype=float), np.linspace(0, 100, 101)).tolist()
        print(f"NDMI: {len(nf):,} baris sel-jendela | jendela terbaru tersedia {nf['available_from'].max().date()}")

    enso_file = out_dir / "enso_monthly.parquet"       # dari 02b_enso.py
    if enso_file.exists():
        enso = pd.read_parquet(enso_file); enso["date"] = pd.to_datetime(enso["date"])
        rain_file = out_dir / "dyn_rain_pixels.parquet"
        d0 = pd.to_datetime(pd.read_parquet(rain_file, columns=["date"])["date"]).min() if rain_file.exists() else pd.Timestamp("2012-01-01")
        d1 = pd.Timestamp.today().normalize()
        dates = pd.date_range(d0, d1, freq="D")
        lag = lagged_for_dates(pd.Series(dates), enso, lag_months=1)         # bulan yang sudah selesai: tanpa kebocoran
        pd.concat([pd.DataFrame({"date": dates}), lag], axis=1).to_parquet(out_dir / "dyn_enso_daily.parquet", index=False)
        print(f"ENSO/IOD: deret regional harian {dates[0].date()}..{dates[-1].date()} (nilai bulan sebelumnya) -> dyn_enso_daily.parquet")

    if not bands:
        sys.exit("Tidak ada pita yang bisa dibuat (data mentah kosong atau anomali belum tersedia karena riwayat < 3 tahun).")
    names = [b for b in BANDS if b in bands]
    with rasterio.open(grid / "dynamic.tif", "w", driver="GTiff", height=shape[0], width=shape[1], count=len(names), dtype="float32", crs=grid_crs(),
                       transform=from_origin(meta["x0"], meta["y_top"], res, res), nodata=np.nan, compress="lzw") as dst:
        for i, n in enumerate(names, 1):
            dst.write(bands[n], i)
            dst.set_band_description(i, n)
    for n in names:
        info[n]["sel_bernilai"] = float(np.isfinite(bands[n]).mean())
    (grid / "dynamic_meta.json").write_text(json.dumps({"dibuat": datetime.now(timezone.utc).isoformat(timespec="seconds"), "pita": info}, indent=1, ensure_ascii=False))
    (grid / "dynamic_reference.json").write_text(json.dumps(reference))
    print("dynamic.tif:", {n: f"{info[n]['sel_bernilai']:.0%} sel, {info[n]['tanggal']}" for n in names})


if __name__ == "__main__":
    main()
