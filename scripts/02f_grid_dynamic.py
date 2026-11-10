"""02f_grid_dynamic: data dinamis mentah per sel dari Earth Engine: hujan harian GSMaP, kelembapan tanah ERA5-Land, dan komposit NDMI Sentinel-2.

    python scripts/02f_grid_dynamic.py --dry-run
    python scripts/02f_grid_dynamic.py --only gsmap,era5soil --start 2015-01-01
    python scripts/02f_grid_dynamic.py --only ndmi --ndmi-step 30

Masuk : data/features/grid/{static,risk_class}.tif dan grid_meta.json (07, 08) untuk sel yang dinilai; Earth Engine (gee.project di config.yaml)
Keluar: data/features/grid_dynamic/rain_pixels.parquet   pixel_id, lon, lat, date, rain_mm            (GSMaP v8 operasional, hari lokal WIB, piksel 0,1 derajat)
        data/features/grid_dynamic/soil_pixels.parquet   pixel_id, lon, lat, date, soil_moisture      (ERA5-Land, lapisan 0-7 cm, m3/m3, hari UTC)
        data/features/grid_dynamic/ndmi_cells.parquet    cx, cy, window_start, window_end, ndmi       (median NDMI per jendela, rata-rata ke sel 1 km)
Lanjutkan dengan 02g_dynamic_features.py (fitur kausal dan dynamic.tif).

Cara kerja yang disengaja:
  - Hujan dan kelembapan tanah diambil di PUSAT PIKSEL produk (satu titik per piksel 0,1 derajat, bukan satu titik per sel), dengan transformasi piksel dibaca
    dari Earth Engine; tiap sel 1 km nanti memakai piksel terdekatnya. Satu permintaan untuk puluhan piksel, bukan ribuan sel.
  - Hujan memakai fungsi extract_gsmap di 02_gee_features.py (definisi yang sama dengan fitur stasiun: jumlah per jam pada hari lokal WIB).
  - NDMI memakai definisi 02_gee_features.build_s2 (B8 dan B11, Cloud Score+ >= 0,6, median), tetapi sebagai raster per jendela (satu permintaan per jendela, bukan
    per sel). Komposit tersedia SETELAH jendelanya berakhir (window_end), bukan sebelumnya.
  - Pembaruan inkremental: hanya tanggal sesudah data terakhir (dikurangi --overlap-days) yang diminta ulang; berkas lama tidak ditulis ulang di luar itu.
Batasan: kelembapan tanah ERA5-Land adalah keluaran model reanalisis dengan hidrologi tanah mineral umum, BUKAN pengamatan dan tidak memodelkan gambut;
perlakukan sebagai petunjuk iklim lapisan atas. Tanggal terakhir yang tersedia di Earth Engine berubah-ubah; skrip memotong sampai tanggal terakhir yang tersedia.
BELUM diuji terhadap Earth Engine sungguhan (bagian lokal diuji dengan data tiruan); jalankan --dry-run lalu satu bulan dulu dan periksa kuota EECU.
"""
import argparse
import importlib.util
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from rasterio.transform import from_origin
from rasterio.warp import Resampling

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.cells import cell_grid_lonlat, load_universe  # noqa: E402
from src.common import load_config, path  # noqa: E402
from src.gee_grid import merge_first, read_download, tiles_for_bbox, to_master  # noqa: E402
from src.gee_utils import date_chunks, date_windows, parse_daily_bands  # noqa: E402
from src.grid import grid_crs  # noqa: E402

GROUPS = ("gsmap", "era5soil", "ndmi")
SOIL_BAND = "volumetric_soil_water_layer_1"


def _module02():
    spec = importlib.util.spec_from_file_location("gee02", Path(__file__).with_name("02_gee_features.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pixel_points(transform, lon: np.ndarray, lat: np.ndarray) -> pd.DataFrame:
    """Piksel unik produk yang memuat titik (lon, lat), dengan pusat piksel. transform = [sx, 0, tx, 0, sy, ty] dari projection() Earth Engine."""
    sx, _, tx, _, sy, ty = transform
    i = np.floor((lon - tx) / sx).astype(int)
    j = np.floor((lat - ty) / sy).astype(int)       # sy negatif
    uniq = pd.DataFrame({"i": i, "j": j}).drop_duplicates().reset_index(drop=True)
    uniq["lon"] = tx + (uniq["i"] + 0.5) * sx
    uniq["lat"] = ty + (uniq["j"] + 0.5) * sy
    uniq["station_id"] = uniq["i"].astype(str) + "_" + uniq["j"].astype(str)       # nama kolom mengikuti fungsi ekstraksi stasiun
    return uniq[["station_id", "lon", "lat"]]


def product_transform(ee, collection: str, band: str):
    return ee.ImageCollection(collection).select(band).first().projection().getInfo()["transform"]


def last_available_day(ee, collection: str) -> date:
    ms = ee.ImageCollection(collection).aggregate_max("system:time_start").getInfo()
    return pd.to_datetime(ms, unit="ms").date()


def extract_era5_soil(ee, pts: pd.DataFrame, start: date, end: date, chunk_days: int) -> pd.DataFrame:
    """Kelembapan tanah lapisan 1 (0-7 cm) harian di titik; definisi sama dengan extract_chirps (toBands + reduceRegions)."""
    gee02 = _module02()
    fc, frames = gee02.points_fc(ee, pts, 0), []
    for s, e in date_chunks(start, end, chunk_days):
        ic = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR").filterDate(str(s), str(e + timedelta(days=1))).select(SOIL_BAND)
        n = ic.size().getInfo()
        if n == 0:
            print(f"  era5soil {s}..{e}: belum tersedia, dilewati")
            continue
        feats = gee02.reduce_at(ee, ic.toBands(), fc, ee.Reducer.first(), 11132)
        frames.append(parse_daily_bands(feats, SOIL_BAND))
        print(f"  era5soil {s}..{e}: {n} citra")
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["station_id", "date", SOIL_BAND])
    return df.rename(columns={SOIL_BAND: "soil_moisture"})


def with_pixels(df: pd.DataFrame, pts: pd.DataFrame, value_col: str) -> pd.DataFrame:
    out = df.merge(pts, on="station_id", how="left").rename(columns={"station_id": "pixel_id"})
    return out[["pixel_id", "lon", "lat", "date", value_col]]


def merge_incremental(existing: pd.DataFrame | None, new: pd.DataFrame, keys=("pixel_id", "date")) -> pd.DataFrame:
    """Gabungkan data baru ke data lama; pada kunci yang sama, data baru menang (koreksi data NRT). Urutan deterministik."""
    if existing is None or existing.empty:
        merged = new
    else:
        merged = pd.concat([existing, new], ignore_index=True).drop_duplicates(list(keys), keep="last")
    return merged.sort_values(list(keys)).reset_index(drop=True)


def fetch_start(existing: pd.DataFrame | None, start: date, overlap_days: int) -> date:
    if existing is None or existing.empty:
        return start
    return max(start, existing["date"].max().date() - timedelta(days=overlap_days))


def fetch_ndmi_tile(ee, bbox, s_, e_, scale_m: float):
    region = ee.Geometry.Rectangle(list(bbox))
    coll = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(region).filterDate(str(s_), str(e_))
    if coll.size().getInfo() == 0:
        return None
    cloud = ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED")
    masked = coll.linkCollection(cloud, ["cs_cdf"]).map(lambda im: im.updateMask(im.select("cs_cdf").gte(0.6)))
    ndmi = masked.map(lambda im: im.normalizedDifference(["B8", "B11"]).rename("ndmi")).median()
    img = ndmi.reduceResolution(reducer=ee.Reducer.mean(), maxPixels=1024).reproject(crs="EPSG:4326", scale=scale_m).toFloat()
    url = img.getDownloadURL({"region": region, "scale": scale_m, "crs": "EPSG:4326", "format": "GEO_TIFF"})
    r = requests.get(url, timeout=600)
    r.raise_for_status()
    return r.content


def ndmi_to_cells(contents: list, uni: dict, s_, e_) -> pd.DataFrame:
    """Unduhan NDMI (EPSG:4326) -> rata-rata ke sel 1 km grid induk -> tabel sel."""
    hh, ww = uni["shape"]
    dst_t = from_origin(uni["cx0"] * 1000.0, (uni["cy_top"] + 1) * 1000.0, 1000.0, 1000.0)
    arr = np.full((hh, ww), np.nan, dtype="float32")
    for content in contents:
        for a, tr, crs, _names in read_download(content, ["ndmi"]):
            arr = merge_first(arr, to_master(a[0], tr, crs, dst_t, (hh, ww), grid_crs(), Resampling.average))
    rr, cc = np.nonzero(uni["valid"] & np.isfinite(arr))
    return pd.DataFrame({"cx": uni["cx0"] + cc, "cy": uni["cy_top"] - rr, "window_start": pd.Timestamp(s_), "window_end": pd.Timestamp(e_), "ndmi": arr[rr, cc]})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", default="gsmap,era5soil", help=f"kelompok dipisah koma dari {GROUPS}")
    ap.add_argument("--start", default="2015-01-01"); ap.add_argument("--end", default=datetime.now(timezone.utc).date().isoformat())
    ap.add_argument("--chunk-days", type=int, default=60); ap.add_argument("--overlap-days", type=int, default=3)
    ap.add_argument("--ndmi-step", type=int, default=30, help="lebar jendela komposit NDMI (hari)"); ap.add_argument("--ndmi-scale", type=float, default=250.0)
    ap.add_argument("--tile-deg", type=float, default=1.0); ap.add_argument("--rain-tz-offset", type=int, default=7)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    groups = [g.strip() for g in args.only.split(",") if g.strip()]
    if set(groups) - set(GROUPS):
        sys.exit(f"Kelompok tidak dikenal: {set(groups) - set(GROUPS)}")
    grid_dir = path("features") / "grid"
    for need in ("grid_meta.json", "static.tif"):
        if not (grid_dir / need).exists():
            sys.exit(f"{need} tidak ada. Jalankan 07_grid_static.py dulu.")
    uni = load_universe(grid_dir)
    lon_c, lat_c = cell_grid_lonlat(uni)
    lon, lat = lon_c[uni["valid"]], lat_c[uni["valid"]]
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    out_dir = path("features") / "grid_dynamic"
    out_dir.mkdir(parents=True, exist_ok=True)
    bbox = (float(lon.min()) - 0.05, float(lat.min()) - 0.05, float(lon.max()) + 0.05, float(lat.max()) + 0.05)
    print(f"sel bernilai {int(uni['valid'].sum()):,} | bbox {tuple(round(v, 3) for v in bbox)} | rentang {start}..{end} | kelompok {groups}")
    if args.dry_run:
        print(f"perkiraan: hujan dan tanah {len(date_chunks(start, end, args.chunk_days))} permintaan per kelompok; NDMI {len(date_windows(start, end, args.ndmi_step))} jendela x "
              f"{len(tiles_for_bbox(bbox, args.tile_deg))} ubin. (dry-run: tidak menyentuh Earth Engine)")
        return
    import ee  # noqa: PLC0415
    project = load_config()["gee"]["project"]
    if "GANTI" in project:
        sys.exit("Isi gee.project di config.yaml dulu.")
    ee.Initialize(project=project)
    gee02 = _module02()

    for group in groups:
        t0 = time.time()
        if group in ("gsmap", "era5soil"):
            coll, band = ("JAXA/GPM_L3/GSMaP/v8/operational", "hourlyPrecipRate") if group == "gsmap" else ("ECMWF/ERA5_LAND/DAILY_AGGR", SOIL_BAND)
            pts = pixel_points(product_transform(ee, coll, band), lon, lat)
            target = out_dir / ("rain_pixels.parquet" if group == "gsmap" else "soil_pixels.parquet")
            existing = pd.read_parquet(target) if target.exists() else None
            s_ = fetch_start(existing, start, args.overlap_days)
            e_ = min(end, last_available_day(ee, coll)) if group == "era5soil" else end
            if s_ > e_:
                print(f"[{group}] sudah mutakhir sampai {e_}")
                continue
            print(f"[{group}] {len(pts)} piksel, {s_}..{e_}")
            if group == "gsmap":
                df = with_pixels(gee02.extract_gsmap(ee, pts, s_, e_, args.chunk_days, args.rain_tz_offset), pts, "rain_mm")
            else:
                df = with_pixels(extract_era5_soil(ee, pts, s_, e_, args.chunk_days), pts, "soil_moisture")
            if df.empty:
                print(f"[{group}] HASIL KOSONG: tidak ditulis.")
                continue
            merge_incremental(existing, df).to_parquet(target, index=False)
            print(f"[{group}] +{len(df)} baris -> {target.name} ({time.time() - t0:.0f} detik)")
        else:
            win_dir = out_dir / "ndmi"
            win_dir.mkdir(exist_ok=True)
            done = 0
            for s_, e_ in date_windows(start, end, args.ndmi_step):
                if e_ > end + timedelta(days=1):
                    continue                                   # jendela belum berakhir
                f = win_dir / f"{s_}.parquet"
                if f.exists():
                    continue
                contents = [c for c in (fetch_ndmi_tile(ee, tb, s_, e_, args.ndmi_scale) for tb in tiles_for_bbox(bbox, args.tile_deg)) if c]
                if not contents:
                    print(f"  jendela {s_}: tidak ada citra")
                    continue
                ndmi_to_cells(contents, uni, s_, e_).to_parquet(f, index=False)
                done += 1
                print(f"  jendela {s_}..{e_}: tersimpan")
            parts = sorted(win_dir.glob("*.parquet"))
            if parts:
                pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True).to_parquet(out_dir / "ndmi_cells.parquet", index=False)
            print(f"[ndmi] {done} jendela baru, total {len(parts)} -> ndmi_cells.parquet ({time.time() - t0:.0f} detik)")
    print("\nPantau pemakaian EECU di Cloud Console setelah uji pertama sebelum menjalankan penuh.")


if __name__ == "__main__":
    main()
