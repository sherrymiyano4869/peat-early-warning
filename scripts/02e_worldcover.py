"""02e_worldcover: tutupan lahan ESA WorldCover v200 (2021, 10 m) menjadi kelas dominan dan pecahan tiap kelas per sel pada grid induk 100 m.

    python scripts/02e_worldcover.py [--tile-deg 0.4] [--force]

Masuk : data/features/grid/grid_meta.json (07) untuk ukuran dan CRS grid; Earth Engine (gee.project di config.yaml)
Keluar: data/features/grid/lulc.tif  pita: lulc (kelas dominan), frac_10 (pohon), frac_20 (semak), frac_30 (rumput), frac_40 (lahan pertanian), frac_50 (terbangun),
                                     frac_60 (terbuka), frac_80 (air), frac_90 (lahan basah herba), frac_95 (bakau)
        data/features/grid/lulc_meta.json  sumber, versi, tanggal ambil, cakupan

Dipakai 08_susceptibility.py (penutup air, terbangun, bakau) dan 14_fire_model.py (pecahan kelas sebagai fitur statis).
Batasan yang harus dibaca: WorldCover adalah potret 2021 (tidak mencatat pembukaan lahan sesudahnya) dan TIDAK punya kelas sawit; kebun sawit dan hutan gambut
sama-sama tampak "tutupan pohon". Pecahan dihitung di Earth Engine dalam EPSG:4326 (reduceResolution rata-rata) lalu diproyeksikan ulang secara rata-rata ke
grid induk; selisih luas kecil di tepi sel. CC BY 4.0: cantumkan atribusi ESA WorldCover.
BELUM diuji terhadap Earth Engine sungguhan (hanya bagian lokal yang diuji); jalankan dulu pada bbox kecil dan periksa lulc.tif di QGIS.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
import requests
from rasterio.transform import from_origin
from rasterio.warp import Resampling, transform_bounds

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import load_config, path  # noqa: E402
from src.gee_grid import merge_first, read_download, tiles_for_bbox, to_master  # noqa: E402
from src.grid import grid_crs  # noqa: E402

CLASSES = (10, 20, 30, 40, 50, 60, 80, 90, 95)
BANDS = ["lulc"] + [f"frac_{c}" for c in CLASSES]


def fetch_tile(ee, bbox, scale_m: float) -> bytes:
    wc = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")
    frac = ee.Image.cat([wc.eq(c).rename(f"frac_{c}") for c in CLASSES])
    frac = frac.reduceResolution(reducer=ee.Reducer.mean(), maxPixels=4096).reproject(crs="EPSG:4326", scale=scale_m)
    mode = wc.rename("lulc").reduceResolution(reducer=ee.Reducer.mode(), maxPixels=4096).reproject(crs="EPSG:4326", scale=scale_m)
    img = ee.Image.cat([mode, frac]).toFloat()
    url = img.getDownloadURL({"region": ee.Geometry.Rectangle(list(bbox)), "scale": scale_m, "crs": "EPSG:4326", "format": "GEO_TIFF"})
    r = requests.get(url, timeout=600)
    r.raise_for_status()
    return r.content


def assemble_lulc(tiles: list, meta: dict, out_file: Path) -> dict:
    """Ubin unduhan (bytes) -> lulc.tif pada grid induk. Fraksi dirata-ratakan, kelas dominan memakai tetangga terdekat; fraksi dinormalkan jumlah 1."""
    crs = grid_crs()
    res, shape = float(meta["res_m"]), (int(meta["height"]), int(meta["width"]))
    dst_t = from_origin(meta["x0"], meta["y_top"], res, res)
    stack = {b: np.full(shape, np.nan, dtype="float32") for b in BANDS}
    for content in tiles:
        for arr, tr, src_crs, names in read_download(content, BANDS):
            for i, name in enumerate(names):
                mode = Resampling.nearest if name == "lulc" else Resampling.average
                stack[name] = merge_first(stack[name], to_master(arr[i], tr, src_crs, dst_t, shape, crs, mode))
    fr = np.stack([stack[f"frac_{c}"] for c in CLASSES])
    total = np.nansum(fr, axis=0)
    ok = total > 0
    for i, c in enumerate(CLASSES):                      # normalkan agar jumlah pecahan 1 di sel yang bernilai
        stack[f"frac_{c}"] = np.where(ok, stack[f"frac_{c}"] / np.where(ok, total, 1), np.nan).astype("float32")
    with rasterio.open(out_file, "w", driver="GTiff", height=shape[0], width=shape[1], count=len(BANDS), dtype="float32", crs=crs, transform=dst_t,
                       nodata=np.nan, compress="lzw") as dst:
        for i, b in enumerate(BANDS, 1):
            dst.write(stack[b], i)
            dst.set_band_description(i, b)
    return {"cells_with_value": int(ok.sum()), "cells_total": int(ok.size)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tile-deg", type=float, default=0.4, help="lebar ubin unduhan (derajat); kecil bila terkena batas ukuran 32 MB")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    grid = path("features") / "grid"
    out_file = grid / "lulc.tif"
    if out_file.exists() and not args.force:
        sys.exit(f"{out_file} sudah ada (gunakan --force untuk mengulang).")
    if not (grid / "grid_meta.json").exists():
        sys.exit("grid_meta.json tidak ada. Jalankan 07_grid_static.py dulu.")
    meta = json.loads((grid / "grid_meta.json").read_text())
    crs = grid_crs()
    x0, y_top, res = meta["x0"], meta["y_top"], float(meta["res_m"])
    bbox = transform_bounds(crs, "EPSG:4326", x0, y_top - meta["height"] * res, x0 + meta["width"] * res, y_top)
    import ee  # noqa: PLC0415
    project = load_config()["gee"]["project"]
    if "GANTI" in project:
        sys.exit("Isi gee.project di config.yaml dulu.")
    ee.Initialize(project=project)
    tiles = tiles_for_bbox(bbox, args.tile_deg)
    print(f"bbox {tuple(round(v, 3) for v in bbox)} -> {len(tiles)} ubin @ {res:.0f} m")
    contents = []
    for i, tb in enumerate(tiles, 1):
        contents.append(fetch_tile(ee, tb, res))
        print(f"  ubin {i}/{len(tiles)}: {len(contents[-1]) / 1e6:.1f} MB")
    stats = assemble_lulc(contents, meta, out_file)
    (grid / "lulc_meta.json").write_text(json.dumps({"produk": "ESA/WorldCover/v200", "tahun": 2021, "resolusi_sumber_m": 10, "lisensi": "CC BY 4.0",
                                                     "diambil": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "bbox": list(bbox), **stats,
                                                     "catatan": "Potret 2021; tanpa kelas sawit; fraksi dihitung rata-rata di EPSG:4326 lalu diproyeksikan ulang."}, indent=1, ensure_ascii=False))
    print(f"sel bernilai {stats['cells_with_value']:,} dari {stats['cells_total']:,} | tersimpan {out_file}")


if __name__ == "__main__":
    main()
